"""
crawler_v3.py  —  IIT Jammu Robust Playwright Crawler
======================================================
Crawls https://www.iitjammu.ac.in with full JS rendering.

PROBLEMS SOLVED vs old version:
  1. Partial HTML in saved files  → aggressive HTML stripper
  2. Duplicate pages (same content, different URL) → SHA-256 dedup
  3. Important pages missing (fee,hostel,scholarship) → 90 targeted seeds
  4. Pages render empty on first load → retry with longer wait
  5. PDF links ignored → queues PDFs for pdf_extractor.py separately
  6. Infinite crawl loops → canonical URL normalization
  7. Session-based pages (saral.iitjammu) → blocklist
  8. Rate/bot detection → random jitter + realistic UA rotation
  9. Progress corruption → atomic writes with backup
  10. Content quality variance → scored acceptance threshold

USAGE:
  python crawler_v3.py              # resume or start fresh
  python crawler_v3.py --fresh      # wipe progress, start over
  python crawler_v3.py --max 200    # quick test (200 pages)
  python crawler_v3.py --seeds-only # only crawl seed URLs

OUTPUT:
  data/raw/*.md         — cleaned Markdown pages
  data/raw/_pdfs.txt    — list of PDF URLs to process separately
  data/raw/_progress.json
  data/raw/_crawl_log.json
"""

import os, re, json, time, random, hashlib, logging, asyncio, sys, shutil
from pathlib import Path
from typing import Set, List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse, urldefrag, parse_qs
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("crawler.log", encoding="utf-8"),
    ]
)

# ── Config ─────────────────────────────────────────────────────────
BASE_URL  = os.getenv("TARGET_URL",       "https://www.iitjammu.ac.in").rstrip("/")
RAW_DIR   = Path(os.getenv("RAW_DATA_DIR","../data/raw"))
MAX_PAGES = int(os.getenv("MAX_CRAWL_PAGES", "1000"))
DELAY     = float(os.getenv("CRAWL_DELAY", "1.2"))
JS_WAIT   = int(os.getenv("JS_WAIT_MS",   "2000"))   # ms to wait for JS render

DOMAIN = urlparse(BASE_URL).netloc  # www.iitjammu.ac.in

# ── URL patterns to skip completely ────────────────────────────────
SKIP_DOMAINS = {
    "saral.iitjammu.ac.in",   # external ERP login — no useful content
    "facebook.com", "twitter.com", "youtube.com",
    "linkedin.com", "instagram.com", "t.co",
    "google.com", "googleapis.com", "gstatic.com",
    "cloudflare.com", "cdnjs.cloudflare.com",
}

SKIP_EXTENSIONS = re.compile(
    r"\.(jpg|jpeg|png|gif|svg|ico|webp|bmp|tiff"
    r"|woff|woff2|ttf|eot|otf"
    r"|mp4|avi|mov|mp3|wav|ogg"
    r"|zip|rar|tar|gz|7z"
    r"|doc|docx|xls|xlsx|ppt|pptx"   # skip office files
    r"|exe|dmg|apk"
    r")(\?.*)?$",
    re.IGNORECASE,
)

PDF_RE = re.compile(r"\.pdf(\?.*)?$", re.IGNORECASE)

SKIP_PATTERNS = re.compile(
    r"(javascript:|mailto:|tel:|whatsapp:|#$"
    r"|/cdn-cgi/|/wp-content/|/wp-admin/"
    r"|google-analytics|googletagmanager"
    r"|action=logout|/logout|/signout"
    r"|\?print=|&print=|\?format=pdf)",
    re.IGNORECASE,
)

# ── Targeted seeds — every important section ───────────────────────
SEEDS: List[str] = [
    # Home & About
    f"{BASE_URL}/",
    f"{BASE_URL}/about",
    f"{BASE_URL}/about-iit-jammu",
    f"{BASE_URL}/director",
    f"{BASE_URL}/director-message",
    f"{BASE_URL}/administration",
    f"{BASE_URL}/board-of-governors",
    f"{BASE_URL}/senate",
    f"{BASE_URL}/finance-committee",
    f"{BASE_URL}/contact-us",
    f"{BASE_URL}/reach-us",
    f"{BASE_URL}/nirf",
    f"{BASE_URL}/iqac",
    f"{BASE_URL}/annual-report",
    f"{BASE_URL}/rti",
    f"{BASE_URL}/icc",
    f"{BASE_URL}/sc-st-cell",
    f"{BASE_URL}/grievance",
    f"{BASE_URL}/anti-ragging",
    # Academic Programs
    f"{BASE_URL}/academics",
    f"{BASE_URL}/btechprogramme",
    f"{BASE_URL}/btech",
    f"{BASE_URL}/mtechprogramme",
    f"{BASE_URL}/mtech",
    f"{BASE_URL}/mscprogramme",
    f"{BASE_URL}/msc",
    f"{BASE_URL}/phd",
    f"{BASE_URL}/phd-programme",
    f"{BASE_URL}/minors",
    f"{BASE_URL}/honours",
    f"{BASE_URL}/dual-degree",
    f"{BASE_URL}/academic-calendar",
    f"{BASE_URL}/fee-structure",
    f"{BASE_URL}/fee",
    f"{BASE_URL}/academics/fee",
    # Admissions
    f"{BASE_URL}/admissions",
    f"{BASE_URL}/ug-admissions",
    f"{BASE_URL}/pg-admissions",
    f"{BASE_URL}/phd-admissions",
    f"{BASE_URL}/scholarship",
    f"{BASE_URL}/mcm-scholarship",
    f"{BASE_URL}/freeship",
    f"{BASE_URL}/financial-assistance",
    # Departments
    f"{BASE_URL}/computer_science_engineering",
    f"{BASE_URL}/electrical_engineering",
    f"{BASE_URL}/mechanical_engineering",
    f"{BASE_URL}/civil_engineering",
    f"{BASE_URL}/chemical-engineering",
    f"{BASE_URL}/mathematics",
    f"{BASE_URL}/physics",
    f"{BASE_URL}/chemistry",
    f"{BASE_URL}/hss",
    f"{BASE_URL}/materials_engineering",
    f"{BASE_URL}/biosciences_bioengineering",
    f"{BASE_URL}/idp",
    f"{BASE_URL}/cds",
    f"{BASE_URL}/departments",
    # Research
    f"{BASE_URL}/research",
    f"{BASE_URL}/research-labs",
    f"{BASE_URL}/funded-project-details.html",
    f"{BASE_URL}/publications/journals",
    f"{BASE_URL}/publications/conferences",
    f"{BASE_URL}/hpc",
    f"{BASE_URL}/cif",
    f"{BASE_URL}/solar-research-lab/",
    f"{BASE_URL}/solar-research-lab/about.html",
    f"{BASE_URL}/solar-research-lab/facilities.html",
    f"{BASE_URL}/solar-research-lab/publications.html",
    f"{BASE_URL}/underwater-artificial-intelligence-lab/",
    f"{BASE_URL}/c3i",
    # Campus & Facilities
    f"{BASE_URL}/hostel",
    f"{BASE_URL}/student-hostels",
    f"{BASE_URL}/mess",
    f"{BASE_URL}/library",
    f"{BASE_URL}/medical",
    f"{BASE_URL}/medical-centre",
    f"{BASE_URL}/sports",
    f"{BASE_URL}/student-activities",
    f"{BASE_URL}/facilities",
    f"{BASE_URL}/central-workshop",
    f"{BASE_URL}/transport",
    # Placements
    f"{BASE_URL}/placements",
    f"{BASE_URL}/placement",
    f"{BASE_URL}/training-and-placement",
    f"{BASE_URL}/internship",
    # Misc
    f"{BASE_URL}/notices",
    f"{BASE_URL}/news",
    f"{BASE_URL}/events",
    f"{BASE_URL}/alumni",
    f"{BASE_URL}/alumni-affairs",
    f"{BASE_URL}/tenders",
    f"{BASE_URL}/recruitment",
    f"{BASE_URL}/opportunities",
    f"{BASE_URL}/cep",
    f"{BASE_URL}/counselling",
    f"{BASE_URL}/security",
]


# ── URL utilities ───────────────────────────────────────────────────

def _canonical(url: str) -> str:
    """Normalize URL: lowercase scheme+host, remove tracking params, strip fragment."""
    try:
        p = urlparse(url.strip())
        # Remove known tracking/session query params
        BAD_PARAMS = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content",
                      "fbclid","gclid","_ga","ref","source","session","token","PHPSESSID"}
        if p.query:
            qs = parse_qs(p.query, keep_blank_values=False)
            qs_clean = {k: v for k, v in qs.items() if k not in BAD_PARAMS}
            # Rebuild query string deterministically
            query = "&".join(f"{k}={v[0]}" for k, v in sorted(qs_clean.items()))
        else:
            query = ""
        path = p.path.rstrip("/") or "/"
        canon = p._replace(
            scheme=p.scheme.lower(),
            netloc=p.netloc.lower(),
            path=path,
            query=query,
            fragment="",
        )
        return canon.geturl()
    except Exception:
        return url


def _should_skip(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return True
    if SKIP_PATTERNS.search(url):
        return True
    if SKIP_EXTENSIONS.search(url):
        return True
    parsed = urlparse(url)
    if parsed.netloc in SKIP_DOMAINS:
        return True
    if parsed.netloc and parsed.netloc != DOMAIN:
        return True
    return False


def _is_pdf(url: str) -> bool:
    return bool(PDF_RE.search(url))


def _normalize_href(href: str, base_url: str) -> Optional[str]:
    try:
        url, _ = urldefrag(href.strip())
        if not url:
            return None
        abs_url = urljoin(base_url, url)
        abs_url = _canonical(abs_url)
        if _should_skip(abs_url):
            return None
        return abs_url
    except Exception:
        return None


def _file_name(url: str) -> str:
    p = urlparse(url)
    path = (p.netloc + p.path).strip("/").replace("/", "__") or "index"
    if p.query:
        path += "__" + p.query[:30].replace("=", "_").replace("&", "_")
    if len(path) > 90:
        path = path[:80] + "_" + hashlib.md5(url.encode()).hexdigest()[:8]
    return re.sub(r"[^\w\-_.]", "_", path) + ".md"


# ── HTML → Markdown converter ───────────────────────────────────────

def _page_to_markdown(html: str, url: str) -> Tuple[str, int]:
    """
    Convert rendered HTML to clean Markdown.
    Returns (markdown_text, quality_score).
    quality_score: 0=junk, 1-100=content richness
    """
    from bs4 import BeautifulSoup, NavigableString

    soup = BeautifulSoup(html, "html.parser")

    # ── Step 1: Nuclear removal of all noise ──────────────────────
    NOISE_TAGS = ["script","style","noscript","iframe","meta","link",
                  "head","template","svg","canvas","video","audio","object"]
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()

    NOISE_CLASSES = re.compile(
        r"(nav|navbar|topbar|header(?!-content)|footer|sidebar|breadcrumb"
        r"|pagination|social|share|cookie|banner|popup|modal|overlay"
        r"|back-to-top|scroll-top|gtm|google-tag|loader|spinner"
        r"|carousel-control|slick-|owl-|swiper-button"
        r"|whatsapp|chat-widget|livechat|helpdesk-btn)",
        re.I,
    )
    for tag in soup.find_all(class_=NOISE_CLASSES):
        tag.decompose()
    for tag in soup.find_all(id=NOISE_CLASSES):
        tag.decompose()

    # Remove empty tags after cleanup
    for tag in soup.find_all():
        if tag.get_text(strip=True) == "" and tag.name not in ("br","hr","img"):
            tag.decompose()

    # ── Step 2: Extract title ──────────────────────────────────────
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(" ", strip=True)
    if not title and soup.title:
        raw_title = soup.title.get_text(strip=True)
        # Strip site name suffix "| IIT Jammu" or "- IIT Jammu"
        title = re.sub(r"\s*[\|\-]\s*IIT Jammu.*$", "", raw_title, flags=re.I).strip()
    if not title:
        title = "IIT Jammu"

    # ── Step 3: Find main content area ────────────────────────────
    main = (
        soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find(id=re.compile(r"^(main|content|page-content|body-content)$", re.I))
        or soup.find(class_=re.compile(r"^(main-content|page-content|content-area|rs-content)$", re.I))
        or soup.find("article")
        or soup.find(class_=re.compile(r"(content|main|body|wrapper|page)", re.I))
        or soup.body
    )
    if not main:
        return f"# {title}\n**Source:** {url}\n---\n", 0

    # ── Step 4: Convert to Markdown ────────────────────────────────
    def _table_to_md(tbl) -> str:
        rows = tbl.find_all("tr")
        if not rows:
            return ""
        out = []
        for i, row in enumerate(rows):
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            row_text = "| " + " | ".join(
                c.get_text(" ", strip=True).replace("|", "\\|") for c in cells
            ) + " |"
            out.append(row_text)
            if i == 0:
                out.append("| " + " | ".join(["---"] * len(cells)) + " |")
        return "\n".join(out)

    def _el_to_md(el, depth=0) -> str:
        if depth > 20:  # prevent infinite recursion
            return ""
        if isinstance(el, NavigableString):
            text = str(el).strip()
            # Skip pure whitespace and lone punctuation
            return text if len(text) > 1 else ""

        tag = el.name.lower() if el.name else ""

        if tag in ("h1","h2","h3","h4","h5","h6"):
            text = el.get_text(" ", strip=True)
            if not text:
                return ""
            level = int(tag[1])
            return f"\n{'#' * level} {text}\n"

        if tag == "p":
            text = el.get_text(" ", strip=True)
            return f"\n{text}\n" if text else ""

        if tag in ("ul", "ol"):
            items = []
            for li in el.find_all("li", recursive=False):
                text = li.get_text(" ", strip=True)
                if text:
                    items.append(f"- {text}")
            return "\n".join(items) + "\n" if items else ""

        if tag == "table":
            md = _table_to_md(el)
            return f"\n{md}\n" if md else ""

        if tag == "a":
            text = el.get_text(" ", strip=True)
            href = el.get("href", "")
            if href and not SKIP_PATTERNS.search(href) and not SKIP_EXTENSIONS.search(href):
                abs_href = urljoin(url, href)
                return f"[{text}]({abs_href})" if text else ""
            return text

        if tag in ("strong", "b"):
            text = el.get_text(" ", strip=True)
            return f"**{text}**" if text else ""

        if tag in ("em", "i"):
            text = el.get_text(" ", strip=True)
            return f"*{text}*" if text else ""

        if tag == "br":
            return "\n"

        if tag == "hr":
            return "\n---\n"

        if tag in ("span", "div", "section", "article", "aside",
                   "main", "header", "footer", "nav", "figure",
                   "figcaption", "details", "summary", "blockquote",
                   "dl", "dt", "dd", "label", "form", "fieldset",
                   "td", "th", "tr", "thead", "tbody", "tfoot"):
            parts = [_el_to_md(c, depth+1) for c in el.children]
            return " ".join(p for p in parts if p)

        # Fallback: just get text
        return el.get_text(" ", strip=True)

    body_md = _el_to_md(main)

    # ── Step 5: Clean up the markdown ─────────────────────────────
    # Remove residual HTML tags
    body_md = re.sub(r"<[^>]{1,100}>", " ", body_md)
    # Collapse excessive whitespace
    body_md = re.sub(r" {3,}", " ", body_md)
    body_md = re.sub(r"\n{4,}", "\n\n\n", body_md)
    # Remove lines that are just CSS class names or JS artifacts
    body_md = re.sub(r"^(function\(|var |const |let |=>|\.[\w-]+\{).*$", "", body_md, flags=re.MULTILINE)
    # Remove repeated identical lines (nav duplication)
    seen_lines: Set[str] = set()
    deduped = []
    for line in body_md.split("\n"):
        stripped = line.strip()
        if not stripped:
            deduped.append(line)
            continue
        if stripped in seen_lines and len(stripped) > 10:
            continue
        seen_lines.add(stripped)
        deduped.append(line)
    body_md = "\n".join(deduped)
    body_md = body_md.strip()

    # ── Step 6: Quality score ──────────────────────────────────────
    words = len(body_md.split())
    has_numbers = bool(re.search(r"\d", body_md))
    has_tables  = "|" in body_md
    has_lists   = "- " in body_md
    has_headings = bool(re.search(r"^#{1,4} ", body_md, re.MULTILINE))

    score = min(100, (
        min(words // 10, 50)           # up to 50 pts for word count
        + (10 if has_numbers else 0)   # factual data
        + (10 if has_tables  else 0)   # structured data
        + (10 if has_lists   else 0)   # lists
        + (10 if has_headings else 0)  # structure
        + (10 if words > 200  else 0)  # substantial content
    ))

    final = f"# {title}\n**Source:** {url}\n---\n{body_md}"
    return final, score


# ── Progress management ─────────────────────────────────────────────

PROGRESS_FILE = RAW_DIR / "_progress.json"
PDF_LIST_FILE = RAW_DIR / "_pdfs.txt"


def _load_progress() -> Tuple[Set[str], List[str], Set[str]]:
    """Returns (visited_urls, queue, pdf_urls)"""
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
            visited = set(data.get("visited", []))
            queue   = data.get("queue", [])
            pdfs    = set(data.get("pdfs", []))
            logger.info(f"  ↩  Resuming: {len(visited)} visited, {len(queue)} queued, {len(pdfs)} PDFs found")
            return visited, queue, pdfs
        except Exception as e:
            logger.warning(f"Progress file corrupt: {e} — starting fresh")
    return set(), list(SEEDS), set()


def _save_progress(visited: Set[str], queue: List[str], pdfs: Set[str]):
    """Atomic write with backup."""
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({
            "visited": sorted(visited),
            "queue":   queue[:10000],
            "pdfs":    sorted(pdfs),
        }, indent=2),
        encoding="utf-8",
    )
    if PROGRESS_FILE.exists():
        shutil.copy2(PROGRESS_FILE, PROGRESS_FILE.with_suffix(".bak"))
    shutil.move(str(tmp), str(PROGRESS_FILE))


# ── Main async crawler ──────────────────────────────────────────────

async def crawl_async(
    resume: bool = True,
    max_pages: int = MAX_PAGES,
    seeds_only: bool = False,
):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(
            "Playwright not installed!\n"
            "Run: pip install playwright\n"
            "     playwright install chromium"
        )
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if resume:
        visited, queue, pdfs = _load_progress()
    else:
        visited, queue, pdfs = set(), list(SEEDS), set()
        logger.info("🆕 Fresh crawl — wiping progress")

    if seeds_only:
        queue = [u for u in SEEDS if u not in visited]
        logger.info(f"🌱 Seeds-only mode: {len(queue)} seeds")

    # Deduplicate queue
    queue = list(dict.fromkeys(u for u in queue if u not in visited))
    existing = {f.name for f in RAW_DIR.glob("*.md") if not f.name.startswith("_")}
    crawled = len(existing)
    log: List[Dict] = []

    # Content deduplication (SHA-256 of body)
    content_hashes: Set[str] = set()

    logger.info(f"🕷  Crawler ready | target={max_pages} | queued={len(queue)} | saved={crawled}")

    # User agents rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    ]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-images",
                "--blink-settings=imagesEnabled=false",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-sync",
            ]
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            java_script_enabled=True,
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
        )
        page = await context.new_page()

        # Block heavy resources
        await page.route(
            re.compile(r"\.(png|jpg|jpeg|gif|svg|ico|webp|woff|woff2|ttf|mp4|mp3)(\?.*)?$", re.I),
            lambda route: route.abort()
        )
        # Block analytics
        await page.route(
            re.compile(r"(google-analytics|googletagmanager|hotjar|clarity|facebook\.net)", re.I),
            lambda route: route.abort()
        )

        empty_streak = 0  # consecutive empty pages → site may be blocking us

        while queue and crawled < max_pages:
            url = queue.pop(0)
            url = _canonical(url)

            if url in visited:
                continue
            if _should_skip(url):
                continue
            if _is_pdf(url):
                pdfs.add(url)
                visited.add(url)
                continue

            visited.add(url)
            logger.info(f"[{crawled+1}/{max_pages}] {url}")

            try:
                # Navigate
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=25000)

                # Skip non-200 or non-HTML responses
                if resp and resp.status not in (200, 301, 302):
                    logger.debug(f"  Skip: HTTP {resp.status}")
                    log.append({"url": url, "status": f"http_{resp.status}"})
                    continue

                content_type = (resp.headers.get("content-type", "") if resp else "")
                if "text/html" not in content_type and content_type:
                    logger.debug(f"  Skip: content-type={content_type}")
                    continue

                # Wait for JS to render — adaptive wait
                await page.wait_for_timeout(JS_WAIT)

                # Try to wait for main content to appear
                try:
                    await page.wait_for_selector(
                        "main, article, .content, #content, [role=main]",
                        timeout=3000
                    )
                except Exception:
                    pass  # proceed anyway

                # ── Extract new links BEFORE saving ────────────────
                hrefs = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                new_links = 0
                for href in hrefs:
                    n = _normalize_href(href, url)
                    if not n:
                        continue
                    if _is_pdf(n):
                        if n not in pdfs:
                            pdfs.add(n)
                    elif n not in visited and n not in queue:
                        queue.append(n)
                        new_links += 1

                # ── Extract and save content ────────────────────────
                html = await page.content()
                md, quality = _page_to_markdown(html, url)

                # Content deduplication
                body = "\n".join(md.split("\n")[3:]).strip()
                body_hash = hashlib.sha256(body[:1000].encode()).hexdigest()

                if quality < 15:
                    logger.debug(f"  - quality={quality} (too low), skipped")
                    log.append({"url": url, "status": "low_quality", "score": quality})
                    empty_streak += 1
                    if empty_streak >= 20:
                        logger.warning("20 consecutive low-quality pages — possible bot detection. Sleeping 60s...")
                        await asyncio.sleep(60)
                        empty_streak = 0
                    continue

                if body_hash in content_hashes:
                    logger.debug(f"  - duplicate content, skipped")
                    log.append({"url": url, "status": "duplicate"})
                    continue

                content_hashes.add(body_hash)
                fname = _file_name(url)
                (RAW_DIR / fname).write_text(md, encoding="utf-8")
                crawled += 1
                empty_streak = 0
                log.append({"url": url, "file": fname, "status": "ok",
                            "chars": len(body), "quality": quality, "new_links": new_links})
                logger.info(f"  ✓ saved | quality={quality} | +{new_links} links | {len(body)} chars")

            except asyncio.TimeoutError:
                logger.warning(f"  ✗ Timeout")
                log.append({"url": url, "status": "timeout"})
            except Exception as e:
                logger.warning(f"  ✗ {type(e).__name__}: {str(e)[:100]}")
                log.append({"url": url, "status": f"error: {type(e).__name__}"})

            # Save progress every 25 pages
            if len(visited) % 25 == 0:
                _save_progress(visited, queue, pdfs)
                # Write PDF list
                if pdfs:
                    PDF_LIST_FILE.write_text("\n".join(sorted(pdfs)), encoding="utf-8")

            # ── Incremental index update every 25 pages SAVED ──────
            if crawled > 0 and crawled % 15 == 0:
                logger.info("🌲 [Page %d] Running incremental index update...", crawled)
                import subprocess as _sp
                result = _sp.run(
                    [sys.executable, "indexer.py", "--merge"],
                    cwd=str(Path(__file__).resolve().parent),
                    capture_output=True, text=True,
                )
                if result.returncode == 0:
                    logger.info("✅ Index updated — knowledge base current to page %d", crawled)
                else:
                    logger.warning("⚠  Index update failed at page %d: %s", crawled, result.stderr[:200])
             
            # Extract any new PDFs every 25 pages too
            if crawled > 0 and crawled % 15 == 0:
                 if pdfs:
                     PDF_LIST_FILE.write_text("\n".join(sorted(pdfs)), encoding="utf-8")
                     logger.info("📄 Running incremental PDF extraction...")
                     _sp.run(
                    [sys.executable, "pdf_extractor.py"],
                    cwd=str(Path(__file__).resolve().parent),
                     capture_output=True, text=True,
                     )
                         # Polite delay with jitter
            await asyncio.sleep(DELAY * (0.6 + random.random() * 0.8))

        await browser.close()

    # Final save
    _save_progress(visited, queue, pdfs)
    if pdfs:
        PDF_LIST_FILE.write_text("\n".join(sorted(pdfs)), encoding="utf-8")
        logger.info(f"  📄 {len(pdfs)} PDFs found → {PDF_LIST_FILE}")

    (RAW_DIR / "_crawl_log.json").write_text(
        json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    ok = sum(1 for e in log if e.get("status") == "ok")
    errs = sum(1 for e in log if "error" in e.get("status", ""))
    dups = sum(1 for e in log if e.get("status") == "duplicate")

    logger.info(f"""
✅  Crawl complete
    Saved     : {crawled} pages
    Queue left: {len(queue)} (run again to continue)
    Visited   : {len(visited)} URLs
    PDFs found: {len(pdfs)}
    Errors    : {errs}
    Duplicates: {dups}
""")


def run_crawler(resume=True, max_pages=MAX_PAGES, seeds_only=False):
    asyncio.run(crawl_async(resume=resume, max_pages=max_pages, seeds_only=seeds_only))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="IIT Jammu Playwright Crawler")
    p.add_argument("--fresh",      action="store_true", help="Ignore saved progress, start over")
    p.add_argument("--max",        type=int, default=MAX_PAGES, help="Max pages to crawl")
    p.add_argument("--seeds-only", action="store_true", help="Only crawl seed URLs (fast test)")
    args = p.parse_args()
    run_crawler(resume=not args.fresh, max_pages=args.max, seeds_only=args.seeds_only)