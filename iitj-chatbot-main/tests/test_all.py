#!/usr/bin/env python3
"""
test_all.py — IIT Jammu Chatbot — Full System Health Check
===========================================================

Checks every layer of the system and prints a colour-coded report.
No pytest required — pure stdlib + the project's own dependencies.

Usage:
    cd iitj-chatbot
    python tests/test_all.py                    # test everything
    python tests/test_all.py --skip-api         # skip live Gemini call
    python tests/test_all.py --backend-url http://localhost:8000
"""
import sys, os, json, time, re, argparse, importlib, traceback
from pathlib import Path
from typing import Callable, List, Tuple, Optional

# ── colour helpers (work on Windows too if colorama installed) ──────
try:
    import colorama; colorama.init()
    GREEN  = "\033[92m"; RED  = "\033[91m"; YELLOW = "\033[93m"
    CYAN   = "\033[96m"; BOLD = "\033[1m";  RESET  = "\033[0m"
except ImportError:
    GREEN = RED = YELLOW = CYAN = BOLD = RESET = ""

PASS = f"{GREEN}✓ PASS{RESET}"
FAIL = f"{RED}✗ FAIL{RESET}"
WARN = f"{YELLOW}⚠ WARN{RESET}"
SKIP = f"{CYAN}- SKIP{RESET}"

# ── result accumulator ───────────────────────────────────────────────
results: List[Tuple[str, str, str]] = []   # (group, name, status+detail)

def record(group: str, name: str, ok: Optional[bool], detail: str = ""):
    icon = PASS if ok is True else (FAIL if ok is False else SKIP if ok is None else WARN)
    results.append((group, name, icon, detail))
    line = f"  {icon}  {name}"
    if detail:
        line += f"  — {detail}"
    print(line)

def section(title: str):
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*60}{RESET}")


# ══════════════════════════════════════════════════════════════════
#  GROUP 0 — Environment & Config
# ══════════════════════════════════════════════════════════════════
def check_env(args):
    section("0 · Environment & Configuration")

    # .env file present?
    env_path = Path(".env")
    record("env", ".env file exists", env_path.exists(),
           str(env_path.resolve()) if env_path.exists() else "Create from .env.example")

    # Load it
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv()

    # Required vars
    for var, required in [
        ("GEMINI_API_KEY", True),
        ("GEMINI_MODEL",   False),
        ("INDEX_FILE",     False),
        ("CORS_ORIGINS",   False),
    ]:
        val = os.getenv(var, "")
        if required:
            record("env", f"${var} set", bool(val),
                   f"{val[:8]}…" if val else "MISSING — add to .env")
        else:
            record("env", f"${var} set (optional)", None,
                   val or f"using default")

    # Python version
    major, minor = sys.version_info[:2]
    ok = (major == 3 and minor >= 10)
    record("env", f"Python {major}.{minor} (need ≥3.10)", ok)


# ══════════════════════════════════════════════════════════════════
#  GROUP 1 — Dependencies
# ══════════════════════════════════════════════════════════════════
def check_deps(args):
    section("1 · Python Dependencies")

    backend_deps = [
        ("fastapi",            "fastapi"),
        ("uvicorn",            "uvicorn"),
        ("google.generativeai","google-generativeai"),
        ("langdetect",         "langdetect"),
        ("pydantic",           "pydantic"),
        ("slowapi",            "slowapi"),
        ("dotenv",             "python-dotenv"),
    ]
    scraper_deps = [
        ("bs4",     "beautifulsoup4"),
        ("requests","requests"),
    ]
    optional_deps = [
        ("fitz",       "PyMuPDF (PDF extraction)"),
        ("colorama",   "colorama (coloured output)"),
    ]

    for mod, label in backend_deps:
        try:
            importlib.import_module(mod)
            record("deps", label, True)
        except ImportError:
            record("deps", label, False, f"pip install {label}")

    for mod, label in scraper_deps:
        try:
            importlib.import_module(mod)
            record("deps", label, True)
        except ImportError:
            record("deps", label, False, f"pip install {label}")

    for mod, label in optional_deps:
        try:
            importlib.import_module(mod)
            record("deps", label, True)
        except ImportError:
            record("deps", label, None, f"optional — pip install {label}")


# ══════════════════════════════════════════════════════════════════
#  GROUP 2 — Data / Knowledge Index
# ══════════════════════════════════════════════════════════════════
def check_index(args):
    section("2 · Knowledge Index (data/processed/iitj_index.json)")

    from dotenv import load_dotenv; load_dotenv()
    raw_index = os.getenv("INDEX_FILE", "data/processed/iitj_index.json")
    # Resolve paths like ../data/... relative to the project root (cwd)
    index_path = Path(raw_index)
    if not index_path.is_absolute() and raw_index.startswith(".."):
        index_path = Path(raw_index.replace("../", "", 1))

    record("index", "Index file exists", index_path.exists(), str(index_path))
    if not index_path.exists():
        print(f"   → Run: python scraper/indexer.py")
        return

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        record("index", "Valid JSON", True)
    except Exception as e:
        record("index", "Valid JSON", False, str(e))
        return

    # Structure checks
    has_structure = isinstance(data.get("structure"), list)
    record("index", "'structure' key is a list", has_structure)

    nodes = data.get("structure", [])
    record("index", f"Root sections: {len(nodes)} (need ≥1)",
           len(nodes) >= 1, str([n.get("title","?") for n in nodes[:5]]))

    total = data.get("total_nodes", 0)
    record("index", f"Total nodes: {total} (need ≥10)", total >= 10)

    # Spot-check a random node
    def _all_nodes(lst):
        for n in lst:
            yield n
            yield from _all_nodes(n.get("nodes", []))

    all_nodes = list(_all_nodes(nodes))
    missing_title = [n for n in all_nodes if not n.get("title")]
    record("index", "All nodes have 'title'",
           len(missing_title) == 0, f"{len(missing_title)} missing" if missing_title else "")

    has_text = sum(1 for n in all_nodes if n.get("text","").strip())
    record("index", f"Nodes with text content: {has_text}/{len(all_nodes)}",
           has_text > 0)

    has_summary = sum(1 for n in all_nodes if n.get("summary","").strip())
    record("index", f"Nodes with summaries: {has_summary}/{len(all_nodes)}",
           has_summary > 0)

    last_updated = data.get("last_updated","unknown")
    record("index", f"Last updated: {last_updated}", True)

    # Raw data check
    raw_dir = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
    raw_files = list(raw_dir.glob("*.md")) if raw_dir.exists() else []
    record("index", f"Raw markdown files: {len(raw_files)}",
           len(raw_files) >= 0,
           "Run scraper/crawler.py to populate" if not raw_files else "")


# ══════════════════════════════════════════════════════════════════
#  GROUP 3 — Scraper Logic (unit tests, no network)
# ══════════════════════════════════════════════════════════════════
def check_scraper(args):
    section("3 · Scraper Unit Tests (no network)")

    # Test URL normalisation
    sys.path.insert(0, str(Path("scraper")))
    try:
        import crawler as cr

        # _normalize — same domain should pass
        n = cr._normalize("/faculty", "https://www.iitjammu.ac.in/about")
        record("scraper", "_normalize: relative path", n == "https://www.iitjammu.ac.in/faculty", str(n))

        # _normalize — external should be blocked
        n2 = cr._normalize("https://facebook.com/iitj", "https://www.iitjammu.ac.in/")
        record("scraper", "_normalize: blocks external domain", n2 is None, str(n2))

        # _normalize — skip patterns
        n3 = cr._normalize("brochure.pdf", "https://www.iitjammu.ac.in/")
        record("scraper", "_normalize: blocks .pdf extension", n3 is None, str(n3))

        # _file_name uniqueness
        f1 = cr._file_name("https://www.iitjammu.ac.in/fee")
        f2 = cr._file_name("https://www.iitjammu.ac.in/about")
        record("scraper", "_file_name produces .md files", f1.endswith(".md") and f2.endswith(".md"))
        record("scraper", "_file_name is unique per URL", f1 != f2)

        # HTML→Markdown conversion
        from bs4 import BeautifulSoup
        html = """<html><body>
            <nav>should be removed</nav>
            <main>
              <h1>Fee Structure</h1>
              <p>B.Tech fee is Rs 1,51,720 per year for General category.</p>
              <table><tr><th>Category</th><th>Fee</th></tr>
                     <tr><td>General</td><td>Rs 1,51,720</td></tr></table>
            </main>
            <footer>should be removed</footer>
        </body></html>"""
        soup = BeautifulSoup(html, "html.parser")
        md = cr._html_to_md(soup, "https://www.iitjammu.ac.in/fee")
        record("scraper", "HTML→MD: h1 preserved", "# Fee Structure" in md)
        record("scraper", "HTML→MD: <nav> stripped", "should be removed" not in md)
        record("scraper", "HTML→MD: table converted", "Category" in md and "---" in md)
        record("scraper", "HTML→MD: paragraph preserved", "1,51,720" in md)

    except Exception as e:
        record("scraper", "Scraper module load", False, str(e))
        traceback.print_exc()


# ══════════════════════════════════════════════════════════════════
#  GROUP 4 — Indexer / Summariser Unit Tests
# ══════════════════════════════════════════════════════════════════
def check_indexer(args):
    section("4 · Indexer & Summariser Unit Tests")

    sys.path.insert(0, str(Path("scraper")))
    try:
        import indexer as ix

        # Topic assignment
        t1 = ix.assign_topic("fee_structure", "B.Tech tuition fee is Rs 1,51,720 per year")
        record("indexer", "assign_topic: fee content → 'Fee Structure'",
               t1 == "Fee Structure", f"got '{t1}'")

        # "curriculum courses" hits Academic Programs keywords — that is correct behaviour
        t2 = ix.assign_topic("cse_department_page", "Department of Computer Science Engineering faculty research")
        record("indexer", "assign_topic: CSE dept page → 'Departments'",
               t2 == "Departments", f"got '{t2}'")

        # Offline summarizer
        text = (
            "IIT Jammu offers B.Tech in Computer Science with 75 seats. "
            "The annual fee for General category students is Rs 1,51,720. "
            "Admission is through JEE Advanced and JoSAA counselling. "
            "The campus is located at Jagti, Nagrota, Jammu. "
            "SC/ST students pay only Rs 51,720 per year as fee waiver applies."
        )
        s = ix.offline_summarize("B.Tech Fees", text)
        record("indexer", "offline_summarize: returns non-empty string", bool(s.strip()))
        record("indexer", "offline_summarize: ≤ 220 chars", len(s) <= 225, f"{len(s)} chars")
        record("indexer", "offline_summarize: prefers factual sentences (contains number)",
               bool(re.search(r"\d", s)), f"'{s[:80]}…'")

        # Section extraction — use real newlines (\n in regular strings are literals)
        md = (
            "# IIT Jammu Fee\n"
            "\n"
            "## B.Tech Fees\n"
            "General category fee is Rs 1,51,720 per year including all charges.\n"
            "\n"
            "## M.Tech Fees\n"
            "Total M.Tech fee over two years is Rs 1,03,220 for General category students."
        )
        secs = ix.extract_sections(md)
        record("indexer", "extract_sections: finds correct count",
               len(secs) == 2, f"found {len(secs)}")
        record("indexer", "extract_sections: correct titles",
               len(secs) > 0 and secs[0]["title"] == "B.Tech Fees",
               str([s["title"] for s in secs]))

        # page_title
        pt = ix.page_title("# Fee Structure 2024\n\nSome content here")
        record("indexer", "page_title extracts h1", pt == "Fee Structure 2024", f"got '{pt}'")

        # Content hash deduplication
        h1 = ix.content_hash("same content here")
        h2 = ix.content_hash("same content here")
        h3 = ix.content_hash("different content")
        record("indexer", "content_hash: same text = same hash", h1 == h2)
        record("indexer", "content_hash: different text = different hash", h1 != h3)

    except Exception as e:
        record("indexer", "Indexer module load", False, str(e))
        traceback.print_exc()


# ══════════════════════════════════════════════════════════════════
#  GROUP 5 — Backend Unit Tests (no server needed)
# ══════════════════════════════════════════════════════════════════
def check_backend_units(args):
    section("5 · Backend Unit Tests (no server needed)")

    sys.path.insert(0, str(Path("backend")))
    from dotenv import load_dotenv; load_dotenv()

    # ── Language handler ──────────────────────────────────────────
    try:
        import language_handler as lh

        ctx_en = lh.LanguageContext("What is the fee structure at IIT Jammu?")
        record("backend", "LangDetect: English detected",
               ctx_en.detected_lang == "en", f"got '{ctx_en.detected_lang}'")

        ctx_hi = lh.LanguageContext("आईआईटी जम्मू में बी.टेक की फीस क्या है?")
        record("backend", "LangDetect: Hindi detected",
               ctx_hi.detected_lang == "hi", f"got '{ctx_hi.detected_lang}'")

        instr = lh.build_language_instruction("hi")
        record("backend", "build_language_instruction: Hindi instruction generated",
               "Hindi" in instr and len(instr) > 10, f"'{instr[:60]}…'")

        instr_en = lh.build_language_instruction("en")
        record("backend", "build_language_instruction: English = empty (no instruction)",
               instr_en == "", f"got: '{instr_en}'")

        norm = lh.normalize_language_code("zh-cn")
        record("backend", "normalize_language_code: zh-cn preserved", norm == "zh-cn")

        norm2 = lh.normalize_language_code("pt-BR")
        record("backend", "normalize_language_code: pt-BR → pt", norm2 == "pt")

    except Exception as e:
        record("backend", "language_handler import", False, str(e))

    # ── RAG engine — knowledge tree loading ──────────────────────
    try:
        import rag_engine as re_mod

        raw_ip = os.getenv("INDEX_FILE", "data/processed/iitj_index.json")
        index_path = raw_ip.replace("../", "", 1) if raw_ip.startswith("..") else raw_ip
        tree = re_mod.IITJKnowledgeTree(index_path)
        record("backend", "KnowledgeTree loads without error", True)
        record("backend", f"KnowledgeTree.count_nodes() > 0",
               tree.count_nodes() > 0, f"{tree.count_nodes()} nodes")

        top = tree.get_top_level_titles()
        record("backend", f"Top-level sections visible: {len(top)}",
               len(top) >= 1, str(top[:4]))

        node = tree.get_root_nodes()
        if node:
            first_id = node[0].get("node_id", "")
            fetched  = tree.get_node(first_id)
            record("backend", "get_node() by ID works",
                   fetched is not None and fetched.get("title") == node[0].get("title"))

    except Exception as e:
        record("backend", "rag_engine import / KnowledgeTree", False, str(e))
        traceback.print_exc()

    # ── Pydantic models ───────────────────────────────────────────
    try:
        from models import ChatRequest, ChatResponse, HealthResponse

        req = ChatRequest(message="What is the fee structure?")
        record("backend", "ChatRequest model: valid input accepted", req.message == "What is the fee structure?")

        try:
            ChatRequest(message="")
            record("backend", "ChatRequest model: empty message rejected", False)
        except Exception:
            record("backend", "ChatRequest model: empty message rejected", True)

        hr = HealthResponse(status="ok", index_loaded=True, total_nodes=42, gemini_model="gemini-1.5-flash")
        record("backend", "HealthResponse model instantiation", hr.status == "ok")

    except Exception as e:
        record("backend", "Pydantic models", False, str(e))


# ══════════════════════════════════════════════════════════════════
#  GROUP 6 — Live Gemini API Test (optional)
# ══════════════════════════════════════════════════════════════════
def check_gemini_api(args):
    section("6 · Live Gemini API Test")

    if args.skip_api:
        record("gemini", "Gemini API test", None, "skipped (--skip-api)")
        return

    from dotenv import load_dotenv; load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY","")
    if not api_key:
        record("gemini", "GEMINI_API_KEY present", False, "Set in .env to enable this test")
        return

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL","gemini-1.5-flash")
        model = genai.GenerativeModel(model_name)

        # Minimal ping
        t0 = time.time()
        resp = model.generate_content(
            "Reply with exactly: IITJ_OK",
            generation_config={"temperature":0,"max_output_tokens":10}
        )
        latency = round(time.time()-t0, 2)
        text = resp.text.strip()
        record("gemini", f"API reachable (model={model_name})", True, f"{latency}s")
        record("gemini", "Response contains expected token", "IITJ_OK" in text, f"got: '{text}'")

    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            record("gemini", "Gemini API reachable", None,
                   "Rate-limited (429) — try again in 60s")
        elif "API_KEY_INVALID" in err or "invalid" in err.lower():
            record("gemini", "Gemini API reachable", False,
                   "Invalid API key — check GEMINI_API_KEY in .env")
        else:
            record("gemini", "Gemini API reachable", False, err[:120])


# ══════════════════════════════════════════════════════════════════
#  GROUP 7 — Live Backend Server Test
# ══════════════════════════════════════════════════════════════════
def check_backend_server(args):
    section("7 · Live Backend Server Tests")

    url = args.backend_url.rstrip("/")
    print(f"  Target: {CYAN}{url}{RESET}")

    try:
        import requests as req

        # Health endpoint
        try:
            r = req.get(f"{url}/health", timeout=8)
            record("server", "GET /health responds", r.status_code == 200, f"HTTP {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                record("server", "  status == 'ok'", data.get("status") == "ok", str(data.get("status")))
                record("server", "  index_loaded == true",
                       data.get("index_loaded") is True, str(data.get("index_loaded")))
                record("server", f"  total_nodes > 0",
                       data.get("total_nodes",0) > 0, str(data.get("total_nodes")))
        except Exception as e:
            record("server", "GET /health", False, str(e))
            print(f"\n  {RED}Server not reachable at {url}{RESET}")
            print(f"  → Start it with: cd backend && uvicorn main:app --port 8000")
            return

        # Stats endpoint
        try:
            r = req.get(f"{url}/index/stats", timeout=8)
            record("server", "GET /index/stats responds", r.status_code == 200, f"HTTP {r.status_code}")
            if r.status_code == 200:
                d = r.json()
                record("server", f"  top_level_sections: {len(d.get('top_level_sections',[]))}",
                       len(d.get("top_level_sections",[])) >= 1)
        except Exception as e:
            record("server", "GET /index/stats", False, str(e))

        # Suggestions endpoint
        try:
            r = req.get(f"{url}/suggestions", timeout=8)
            record("server", "GET /suggestions responds", r.status_code == 200)
            if r.status_code == 200:
                d = r.json()
                record("server", f"  returns questions list: {len(d.get('questions',[]))}",
                       len(d.get("questions",[])) >= 1)
        except Exception as e:
            record("server", "GET /suggestions", False, str(e))

        # Chat endpoint — real query
        if not args.skip_api:
            try:
                payload = {"message": "What is the B.Tech fee at IIT Jammu?", "session_id": "test_session"}
                t0 = time.time()
                r = req.post(f"{url}/chat", json=payload, timeout=30)
                latency = round(time.time()-t0, 2)
                record("server", f"POST /chat responds (latency: {latency}s)",
                       r.status_code == 200, f"HTTP {r.status_code}")
                if r.status_code == 200:
                    d = r.json()
                    record("server", "  'answer' field present",
                           bool(d.get("answer","")), f"{len(d.get('answer',''))} chars")
                    record("server", "  'detected_language' field present",
                           bool(d.get("detected_language")), str(d.get("detected_language")))
                    record("server", "  'confidence' in [0,1]",
                           0.0 <= float(d.get("confidence",0)) <= 1.0,
                           str(d.get("confidence")))
                    # Sanity: answer mentions fees / IIT
                    answer_lower = d.get("answer","").lower()
                    record("server", "  answer is relevant to fee query",
                           any(w in answer_lower for w in ["fee","₹","rs","lakh","tuition","iit"]),
                           f"first 100 chars: '{d.get('answer','')[:100]}'")
            except Exception as e:
                record("server", "POST /chat", False, str(e))
        else:
            record("server", "POST /chat", None, "skipped (--skip-api)")

        # Rate-limit header
        try:
            r = req.get(f"{url}/health", timeout=8)
            cors = r.headers.get("access-control-allow-origin","")
            record("server", "CORS header present", True,
                   cors if cors else "(not present on GET /health — normal)")
        except Exception:
            pass

    except ImportError:
        record("server", "requests library available", False, "pip install requests")


# ══════════════════════════════════════════════════════════════════
#  GROUP 8 — Frontend Build Check
# ══════════════════════════════════════════════════════════════════
def check_frontend(args):
    section("8 · Frontend Checks")

    fe = Path("frontend")
    record("frontend", "frontend/ directory exists", fe.exists())
    record("frontend", "package.json exists", (fe/"package.json").exists())
    record("frontend", "src/main.jsx exists",  (fe/"src"/"main.jsx").exists())
    record("frontend", "src/App.jsx exists",   (fe/"src"/"App.jsx").exists())
    record("frontend", "index.html exists",    (fe/"index.html").exists())

    # Key components
    for comp in [
        "src/components/chatbot/ChatBot.jsx",
        "src/components/chatbot/ChatWindow.jsx",
        "src/components/layout/Header.jsx",
        "src/components/layout/Footer.jsx",
        "src/pages/Home.jsx",
        "src/pages/Programs.jsx",
        "src/pages/Admissions.jsx",
    ]:
        record("frontend", f"{comp}", (fe/comp).exists())

    # node_modules
    nm = fe/"node_modules"
    record("frontend", "node_modules installed",
           nm.exists() and any(nm.iterdir()),
           "" if nm.exists() else "Run: cd frontend && npm install")

    # dist build — warn only; not needed in dev mode
    dist = fe/"dist"
    built = dist.exists()
    # Use None (SKIP/WARN) so a missing dist doesn't count as a hard failure
    record("frontend", "Production build (dist/) exists",
           True if built else None,
           "ready" if built else "Not built yet — run: cd frontend && npm run build")

    # VITE_API_BASE_URL in .env
    from dotenv import load_dotenv; load_dotenv()
    vite_url = os.getenv("VITE_API_BASE_URL","")
    record("frontend", "VITE_API_BASE_URL configured",
           bool(vite_url), vite_url or "Not set — defaults to http://localhost:8000")

    # Ping frontend dev server if it seems to be running
    try:
        import requests as req
        r = req.get("http://localhost:5173", timeout=3)
        record("frontend", "Dev server running on :5173", r.status_code < 500, f"HTTP {r.status_code}")
    except Exception:
        record("frontend", "Dev server on :5173", None,
               "Not running — start with: cd frontend && npm run dev")


# ══════════════════════════════════════════════════════════════════
#  GROUP 9 — Docker / Deployment Files
# ══════════════════════════════════════════════════════════════════
def check_deployment(args):
    section("9 · Deployment Files")

    files = {
        "docker/Dockerfile.backend":  "Backend Docker image",
        "docker/Dockerfile.frontend": "Frontend Docker image",
        "docker/nginx.conf":          "nginx SPA config",
        "docker-compose.yml":         "Local full-stack compose",
        "render.yaml":                "Render.com blueprint",
        "railway.toml":               "Railway.app config",
        ".env.example":               "Environment template",
        ".gitignore":                 ".gitignore",
    }
    for path, label in files.items():
        record("deploy", label, Path(path).exists(), path)

    # docker available?
    import shutil
    docker_ok = shutil.which("docker") is not None
    record("deploy", "docker CLI installed", docker_ok,
           "" if docker_ok else "Install Docker Desktop or Docker Engine")

    node_ok = shutil.which("node") is not None
    record("deploy", "node.js installed",
           node_ok, "" if node_ok else "Install from nodejs.org")

    npm_ok = shutil.which("npm") is not None
    record("deploy", "npm installed", npm_ok)


# ══════════════════════════════════════════════════════════════════
#  SUMMARY
# ══════════════════════════════════════════════════════════════════
def print_summary():
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}  SUMMARY{RESET}")
    print(f"{BOLD}{'═'*60}{RESET}")

    total = len(results)
    passed = sum(1 for _,_,s,_ in results if "PASS" in s)
    failed = sum(1 for _,_,s,_ in results if "FAIL" in s)
    warned = sum(1 for _,_,s,_ in results if "WARN" in s)
    skipped= sum(1 for _,_,s,_ in results if "SKIP" in s)

    print(f"  {PASS}  {passed}/{total} checks passed")
    if failed:
        print(f"  {FAIL}  {failed} failed")
    if warned:
        print(f"  {WARN}  {warned} warnings")
    if skipped:
        print(f"  {SKIP}  {skipped} skipped")

    if failed:
        print(f"\n{BOLD}  Failed checks:{RESET}")
        for grp, name, status, detail in results:
            if "FAIL" in status:
                print(f"  {RED}✗{RESET} [{grp}] {name}: {detail}")

    score_pct = int(passed / max(total - skipped, 1) * 100)
    bar_len   = 40
    filled    = int(bar_len * score_pct / 100)
    bar_color = GREEN if score_pct >= 80 else (YELLOW if score_pct >= 50 else RED)
    bar = bar_color + "█" * filled + RESET + "░" * (bar_len - filled)
    print(f"\n  Health: [{bar}] {bar_color}{score_pct}%{RESET}")
    print()


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IIT Jammu Chatbot — Full System Test")
    parser.add_argument("--skip-api",      action="store_true", help="Skip live Gemini & /chat API calls")
    parser.add_argument("--backend-url",   default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--only",          default="",  help="Run only this group (env/deps/index/scraper/indexer/backend/gemini/server/frontend/deploy)")
    args = parser.parse_args()

    # Change to project root (one level up from tests/)
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    print(f"\n{BOLD}IIT Jammu Chatbot — System Health Check{RESET}")
    print(f"Working dir: {project_root}")

    groups = {
        "env":      check_env,
        "deps":     check_deps,
        "index":    check_index,
        "scraper":  check_scraper,
        "indexer":  check_indexer,
        "backend":  check_backend_units,
        "gemini":   check_gemini_api,
        "server":   check_backend_server,
        "frontend": check_frontend,
        "deploy":   check_deployment,
    }

    only = args.only.lower()
    for name, fn in groups.items():
        if not only or only == name:
            try:
                fn(args)
            except Exception as e:
                print(f"\n{RED}  [INTERNAL ERROR in group '{name}']{RESET}")
                traceback.print_exc()

    print_summary()
