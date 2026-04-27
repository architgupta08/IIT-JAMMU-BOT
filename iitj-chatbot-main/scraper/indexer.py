"""
indexer.py  —  Robust IIT Jammu Knowledge Index Builder
=========================================================
MODIFIED: Now supports --merge mode which adds NEW pages to the
existing index instead of rebuilding from scratch. This lets your
knowledge base grow every time you crawl + index.

USAGE:
  python indexer.py            # rebuild from scratch (original behavior)
  python indexer.py --merge    # ADD new MD files to existing index ← USE THIS
  python indexer.py --stats    # show stats without writing
  python indexer.py --dry-run  # build but don't save
"""

import os, re, json, logging, hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from collections import Counter, defaultdict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

RAW_DIR    = Path(os.getenv("RAW_DATA_DIR",       "../data/raw"))
OUT_DIR    = Path(os.getenv("PROCESSED_DATA_DIR", "../data/processed"))
INDEX_FILE = OUT_DIR / "iitj_index.json"
BASE_URL   = "https://www.iitjammu.ac.in"

MIN_NODE_CHARS = 120
MAX_TEXT_CHARS = 3000
MAX_CHILDREN   = 40


# ══════════════════════════════════════════════════════════════════
#  SEED NODES (hardcoded critical facts)
# ══════════════════════════════════════════════════════════════════

SEED_NODES: List[Dict] = [
    {
        "title": "B.Tech Fee Structure 2024-25",
        "topic": "Fee Structure",
        "text": (
            "IIT Jammu B.Tech Fee Structure 2024-25:\n"
            "General/OBC-NCL/EWS: Tuition Fee Rs 1,00,000 per semester + Exam Rs 400 "
            "+ Registration/Gymkhana/Medical/Library Rs 11,320 = Total Rs 1,51,720 per year.\n"
            "SC/ST/PwD: Tuition fee fully waived, pay only Rs 51,720 per year.\n"
            "One-time at admission: Caution Deposit Rs 5,000 (refundable) + "
            "Security Rs 2,500 + Library Security Rs 1,000 + Gymkhana Rs 2,000 = Rs 10,500.\n"
            "Note: Fees revised periodically. Check official website for latest."
        ),
    },
    {
        "title": "M.Tech and Ph.D Fee Structure",
        "topic": "Fee Structure",
        "text": (
            "M.Tech fee at IIT Jammu: General/OBC-NCL: Rs 1,03,220 total (tuition Rs 50,000/semester). "
            "SC/ST/PwD: Rs 3,220 total (tuition waived). GATE-qualified: Teaching Assistantship "
            "stipend Rs 12,400 per month.\n"
            "Ph.D fee: General Rs 86,580 per year; SC/ST: tuition waived.\n"
            "Ph.D Fellowships: PMRF Rs 70,000-80,000/month; Institute Fellowship JRF Rs 31,000/month, "
            "SRF Rs 35,000/month."
        ),
    },
    {
        "title": "Hostel and Mess Charges",
        "topic": "Fee Structure",
        "text": (
            "IIT Jammu Hostel charges:\n"
            "Single occupancy: Rs 60,230 per year.\n"
            "Double occupancy: Rs 41,320 per year.\n"
            "Mess charges: Rs 3,200-3,500 per month (veg and non-veg options).\n"
            "All hostels have 24/7 Wi-Fi (1 Gbps), laundry, common room, study area.\n"
            "Boys: 9 hostels. Girls: 2 hostels."
        ),
    },
    {
        "title": "MCM and Other Scholarships",
        "topic": "Scholarships & Financial Aid",
        "text": (
            "Scholarships at IIT Jammu:\n"
            "1) Merit-cum-Means (MCM): Full tuition waiver + Rs 1,000/month pocket money. "
            "Eligibility: family income below Rs 4.5 lakh/year AND CGPA >= 6.0. "
            "About 25% of students eligible.\n"
            "2) SC/ST Free Studentship: Full tuition fee automatically waived.\n"
            "3) IITJ Need-Based: Up to Rs 50,000/year for economically weaker sections.\n"
            "4) PMRF: Rs 70,000-80,000/month for outstanding PhD scholars.\n"
            "5) External: INSPIRE, CSIR-SRF, UGC-JRF, GATE-TA also available."
        ),
    },
    {
        "title": "B.Tech Programs and Seat Matrix",
        "topic": "Academic Programs",
        "text": (
            "IIT Jammu B.Tech programs (4-year, JEE Advanced):\n"
            "1. Computer Science & Engineering (CSE) — 75 seats\n"
            "2. Electrical Engineering (EE) — 75 seats\n"
            "3. Mechanical Engineering (ME) — 75 seats\n"
            "4. Civil Engineering (CE) — 50 seats\n"
            "5. Chemical Engineering (CHE) — 30 seats\n"
            "6. Mathematics & Computing (M&C) — 40 seats\n"
            "7. Engineering Physics (EP) — 20 seats\n"
            "Total: 365 seats per year. 20% supernumerary seats for girl candidates."
        ),
    },
    {
        "title": "B.Tech Admission via JEE Advanced and JoSAA",
        "topic": "Admissions",
        "text": (
            "B.Tech admission at IIT Jammu:\n"
            "Step 1: Clear JEE Advanced (conducted by IITs annually, usually in June).\n"
            "Step 2: Register on JoSAA (josaa.nic.in) and fill branch preferences.\n"
            "Step 3: Seat allotment based on JEE Advanced rank + category.\n"
            "Step 4: Accept allotted seat and pay acceptance fee.\n"
            "Step 5: Report to campus with documents.\n"
            "Reservations: OBC-NCL 27%, SC 15%, ST 7.5%, EWS 10%, PwD 5%.\n"
            "Approximate General category closing ranks: CSE 2500-3500, "
            "EE 4000-5500, ME 5000-7000, CE 8000-11000, M&C 3500-5000."
        ),
    },
    {
        "title": "M.Tech Admission via GATE",
        "topic": "Admissions",
        "text": (
            "M.Tech admission at IIT Jammu:\n"
            "Requirement: Valid GATE score (no cutoff published; relative ranking used).\n"
            "Process: Apply online → shortlist by GATE score → written test/interview at IITJ.\n"
            "Stipend: Teaching Assistantship Rs 12,400/month for GATE-qualified students.\n"
            "Sponsored: Minimum 2 years work experience, employer-sponsored, GATE not required.\n"
            "Eligibility: B.E./B.Tech with 60% marks (55% for SC/ST).\n"
            "11 M.Tech specializations available across departments."
        ),
    },
    {
        "title": "Ph.D Admission",
        "topic": "Admissions",
        "text": (
            "Ph.D admission at IIT Jammu:\n"
            "Two sessions: January and August, rolling admissions.\n"
            "Eligibility: M.Tech/M.E./M.Sc/B.Tech (for direct PhD) with 60% marks.\n"
            "Selection: Written test + interview at IIT Jammu campus.\n"
            "Fellowship: Institute fellowship Rs 31,000/month (JRF), Rs 35,000/month (SRF).\n"
            "PMRF available: Rs 70,000-80,000/month for exceptional scholars.\n"
            "Foreign nationals: Separate admissions portal."
        ),
    },
    {
        "title": "Placement Statistics 2023-24",
        "topic": "Placements",
        "text": (
            "IIT Jammu Placement Statistics 2023-24:\n"
            "Students placed: 320+\n"
            "Highest CTC: Rs 1.09 Crore per annum\n"
            "Average CTC: Rs 16.4 LPA\n"
            "Median CTC: Rs 12.8 LPA\n"
            "Companies visited: 120+\n"
            "PPO rate: ~35%\n"
            "Branch-wise average: CSE Rs 22.4 LPA, M&C Rs 20.2 LPA, EE Rs 17.1 LPA, "
            "ME Rs 13.5 LPA, CHE Rs 12.0 LPA, CE Rs 11.8 LPA.\n"
            "Top recruiters: Google, Microsoft, Amazon, Samsung, Qualcomm, Flipkart, "
            "Goldman Sachs, JP Morgan, Intel, Adobe, Cisco, TCS, Infosys, L&T, DRDO, ISRO."
        ),
    },
    {
        "title": "Director and Leadership",
        "topic": "About IIT Jammu",
        "text": (
            "Director of IIT Jammu: Prof. Manoj Singh Gaur.\n"
            "Qualification: Ph.D from IIT Kanpur.\n"
            "Research: Distributed systems, cybersecurity, computer networks.\n"
            "Email: director@iitjammu.ac.in\n"
            "Phone: +91-191-257-0066\n"
            "Other leadership: Dean Academics, Dean Research, Dean Student Affairs, "
            "Dean Faculty Affairs, Registrar.\n"
            "Governed by: Board of Governors (apex), Senate (academic), Finance Committee."
        ),
    },
    {
        "title": "Campus Location and Infrastructure",
        "topic": "Campus & Facilities",
        "text": (
            "IIT Jammu Permanent Campus: Jagti, P.O. Nagrota, Jammu - 181221, J&K.\n"
            "Area: 250+ acres.\n"
            "Established: 2016 by Act of Parliament. Mentored by IIT Delhi.\n"
            "Distance: 18 km from Jammu city, 20 km from Jammu Airport, 18 km from Railway Station.\n"
            "Facilities: 11 hostels, Central Library (40,000+ books), Medical Centre, "
            "Sports complex (cricket, football, basketball, volleyball, badminton, TT, gym), "
            "SBI bank branch + ATM, canteen, cafeteria.\n"
            "Internet: 1 Gbps Wi-Fi across campus (NKN connected).\n"
            "Phone: +91-191-257-0066. Email: info@iitjammu.ac.in. Website: iitjammu.ac.in"
        ),
    },
    {
        "title": "About IIT Jammu",
        "topic": "About IIT Jammu",
        "text": (
            "Indian Institute of Technology Jammu (IIT Jammu) established 2016 by Act of Parliament. "
            "One of the new IITs under Ministry of Education, Government of India. "
            "Mentored by IIT Delhi. Permanent campus at Jagti, Nagrota, Jammu - 181221. "
            "250+ acres campus. Institute of National Importance. "
            "Students: 4900+. Faculty: 150+. "
            "NIRF Rank: 51-75 (2024). "
            "12 academic departments: CSE, EE, ME, CE, CHE, Mathematics, Physics, Chemistry, "
            "HSS, Materials Engineering, Biosciences & Bioengineering, Interdisciplinary Studies."
        ),
    },
    {
        "title": "Contact Details",
        "topic": "Contact & Administration",
        "text": (
            "IIT Jammu Contact Information:\n"
            "Address: Jagti, P.O. Nagrota, Jammu - 181221, Jammu & Kashmir, India.\n"
            "Main Phone: +91-191-257-0066\n"
            "Email: info@iitjammu.ac.in\n"
            "Website: https://www.iitjammu.ac.in\n"
            "Director: director@iitjammu.ac.in\n"
            "Admissions: admissions@iitjammu.ac.in\n"
            "Placements: placements@iitjammu.ac.in\n"
            "Dean Academics: dean.academics@iitjammu.ac.in\n"
            "Dean Research: dean.research@iitjammu.ac.in\n"
            "Registrar: registrar@iitjammu.ac.in\n"
            "Chief Warden: chiefwarden@iitjammu.ac.in"
        ),
    },
]


# ══════════════════════════════════════════════════════════════════
#  Text utilities
# ══════════════════════════════════════════════════════════════════

def strip_html(text):
    text = re.sub(r"<(script|style|noscript|template)[^>]*>.*?</\1>", " ", text, flags=re.DOTALL|re.I)
    text = re.sub(r"<[^>]{1,200}>", " ", text)
    text = re.sub(r"&[a-zA-Z0-9#]{1,8};", " ", text)
    text = re.sub(r"\.[a-zA-Z][\w-]+\s*\{[^}]*\}", " ", text)
    text = re.sub(r"(function\s*\(|var\s+\w+\s*=|const\s+\w+\s*=|let\s+\w+\s*=|=>\s*\{)", " ", text)
    return text

def clean_markdown(text):
    text = strip_html(text)
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            clean_lines.append("")
            continue
        if re.match(r"^https?://\S+$", stripped):
            continue
        if re.match(r"^\[.*\]\(https?://[^)]+\)$", stripped):
            continue
        if len(stripped) < 4 and not re.search(r"[a-zA-Z0-9]", stripped):
            continue
        if re.match(r"^[a-z][\w-]+$", stripped) and len(stripped) < 30:
            continue
        clean_lines.append(line)
    text = "\n".join(clean_lines)
    text = re.sub(r" {3,}", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()

def plain_text(text):
    text = strip_html(text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#*_`|>~\\]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

STOPWORDS = {
    "the","a","an","and","or","of","in","to","is","are","was","were","for",
    "on","at","by","this","that","with","from","it","its","be","as","not",
    "have","has","had","he","she","they","we","you","i","will","can","may",
    "all","also","more","about","but","if","so","do","does","did","been",
}

def offline_summarize(title, text, max_chars=250):
    text_plain = plain_text(text)
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text_plain) if len(s.strip()) > 30]
    if not sents:
        return text_plain[:max_chars]
    if len(sents) <= 2:
        return " ".join(sents)[:max_chars]
    freq = Counter()
    for s in sents:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", s.lower())
        freq.update(w for w in words if w not in STOPWORDS)
    title_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", title.lower())) - STOPWORDS
    for tw in title_words:
        freq[tw] = freq.get(tw, 0) + 3
    def score(s):
        words = re.findall(r"\b[a-zA-Z]{3,}\b", s.lower())
        if not words: return 0.0
        return sum(freq.get(w,0) for w in words)/len(words) + (0.5 if re.search(r"\d",s) else 0)
    scored = sorted(enumerate(sents), key=lambda x: score(x[1]), reverse=True)
    indices = sorted([scored[0][0], min(scored[1][0], len(sents)-1)])
    summary = " ".join(sents[i] for i in indices)
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ",1)[0] + "…"
    return summary

def content_fingerprint(text):
    return hashlib.sha256(plain_text(text[:800]).encode()).hexdigest()

_counter = [0]
def new_id():
    _counter[0] += 1
    return f"{_counter[0]:04d}"

def count_nodes(nodes):
    total = 0
    for n in nodes:
        total += 1 + count_nodes(n.get("nodes", []))
    return total


# ══════════════════════════════════════════════════════════════════
#  Topic classifier
# ══════════════════════════════════════════════════════════════════

TAXONOMY = {
    "About IIT Jammu":          {"keywords":["history","establishment","2016","vision","mission","about iit","overview","institute"],"filename_signals":["about","director","history","overview","board","administration"],"weight":1.0},
    "Academic Programs":        {"keywords":["btech","mtech","msc","phd","programme","program","course","curriculum","degree","undergraduate","postgraduate"],"filename_signals":["btech","mtech","msc","phd","programme","program","course","academic"],"weight":1.0},
    "Admissions":               {"keywords":["admission","jee","gate","jam","josaa","cutoff","rank","eligibility","apply","selection","counselling","seat"],"filename_signals":["admission","jee","gate","josaa","counsell","eligib","seat","apply","cutoff"],"weight":1.2},
    "Fee Structure":            {"keywords":["fee","fees","charges","tuition","hostel charges","mess fee","payment","refund","cost","waiver","caution deposit","rs.","rupees"],"filename_signals":["fee","charge","tuition","payment","financial","cost"],"weight":1.5},
    "Departments":              {"keywords":["department","computer science","cse","civil","electrical","mechanical","chemical","mathematics","physics","chemistry","hss","materials","bioscience"],"filename_signals":["computer_science","electrical_engineering","mechanical_engineering","civil_engineering","chemical","mathematics","physics","chemistry","hss","materials","bsbe","idp","cds"],"weight":1.0},
    "Faculty":                  {"keywords":["faculty","professor","assistant professor","associate professor","staff","supervisor"],"filename_signals":["faculty","professor","staff","people"],"weight":1.3},
    "Research":                 {"keywords":["research","publication","journal","conference","sponsored project","patent","funded","grant"],"filename_signals":["research","publication","journal","conference","patent","funded","project"],"weight":1.0},
    "Campus & Facilities":      {"keywords":["campus","hostel","mess","cafeteria","sports","gym","library","wifi","medical","bank","jagti","paloura","accommodation"],"filename_signals":["hostel","mess","cafeteria","sports","gym","library","medical","campus","facility","transport"],"weight":1.0},
    "Placements":               {"keywords":["placement","recruit","company","package","lpa","ctc","salary","internship","hiring","career","job","offer"],"filename_signals":["placement","recruit","internship","tnp","career","job","package"],"weight":1.4},
    "Scholarships & Financial Aid": {"keywords":["scholarship","mcm","merit-cum-means","freeship","financial aid","stipend","fellowship","pmrf","need-based"],"filename_signals":["scholarship","mcm","freeship","financial","fellowship","stipend"],"weight":1.3},
    "Contact & Administration": {"keywords":["contact","address","phone","email","registrar","dean","administration","office","helpdesk"],"filename_signals":["contact","reach","address","phone","email","admin","registrar","dean"],"weight":1.0},
    "Events & Notices":         {"keywords":["event","news","notice","circular","announcement","seminar","workshop","convocation","fest","tender"],"filename_signals":["event","news","notice","circular","announcement","seminar","workshop","convocation"],"weight":0.8},
    "Research Labs & Centers":  {"keywords":["solar","vlsi","electric vehicle","sustainable energy","ai center","underwater","laboratory","lab","facility","equipment"],"filename_signals":["solar","vlsi","ev","underwater","lab","center","centre","facility","cif","hpc"],"weight":1.0},
}

TOPIC_ORDER = [
    "About IIT Jammu","Academic Programs","Admissions","Fee Structure",
    "Scholarships & Financial Aid","Placements","Campus & Facilities",
    "Departments","Faculty","Research","Research Labs & Centers",
    "Contact & Administration","Events & Notices",
]

def assign_topic(filename, content):
    fname_lower = filename.lower()
    sample = plain_text(content[:2000]).lower()
    best_topic, best_score = "About IIT Jammu", 0.0
    for topic, cfg in TAXONOMY.items():
        fname_score = sum(2.0 for sig in cfg["filename_signals"] if sig in fname_lower)
        kw_score    = sum(sample.count(kw) for kw in cfg["keywords"])
        total       = (fname_score + kw_score) * cfg["weight"]
        if total > best_score:
            best_score = total
            best_topic = topic
    return best_topic

def page_title(content):
    for line in content.split("\n")[:6]:
        if line.startswith("# "):
            title = line[2:].strip()
            return re.sub(r"\s*\|\s*IIT Jammu.*$", "", title, flags=re.I).strip()
    return "IIT Jammu Page"

def extract_sections(content):
    sections = []
    current_title, current_level, buf = None, 0, []
    def flush():
        if not current_title: return
        text = clean_markdown("\n".join(buf)).strip()
        if len(text) < MIN_NODE_CHARS: return
        lines = [l for l in text.split("\n") if l.strip()]
        if lines:
            link_lines = sum(1 for l in lines if re.search(r"\[.+\]\(https?://", l))
            if link_lines/len(lines) > 0.7: return
        sections.append({"title":current_title,"level":current_level,"text":text[:MAX_TEXT_CHARS]})
    content_lines = content.split("\n")
    start = 0
    for i, line in enumerate(content_lines[:6]):
        if line.startswith("---"):
            start = i + 1
            break
    for line in content_lines[start:]:
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            if title.lower() in {"iit jammu","indian institute of technology jammu","home","menu","navigation","contents"}:
                current_title = None; buf = []
            else:
                current_title = title; current_level = level; buf = []
        else:
            buf.append(line)
    flush()
    return sections


# ══════════════════════════════════════════════════════════════════
#  ★ NEW: Merge mode — load existing index fingerprints
# ══════════════════════════════════════════════════════════════════

def extract_existing_fingerprints(nodes: List[Dict], fps: Set[str]):
    """Recursively collect fingerprints of all existing nodes."""
    for n in nodes:
        text = n.get("text","") + n.get("title","")
        if text:
            fps.add(content_fingerprint(text))
        extract_existing_fingerprints(n.get("nodes",[]), fps)

def extract_existing_sources(nodes: List[Dict], sources: Set[str]):
    """Collect all source filenames already in the index."""
    for n in nodes:
        src = n.get("source","")
        if src:
            sources.add(src)
        extract_existing_sources(n.get("nodes",[]), sources)

def load_existing_index() -> Optional[Dict]:
    """Load existing index if it exists."""
    if INDEX_FILE.exists():
        try:
            data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            logger.info(f"  Loaded existing index: {data.get('total_nodes',0)} nodes")
            return data
        except Exception as e:
            logger.warning(f"  Could not load existing index: {e}")
    return None

def get_or_create_topic_node(root_nodes: List[Dict], topic: str) -> Dict:
    """Find existing topic node or create a new one."""
    for node in root_nodes:
        if node.get("title") == topic:
            return node
    # Create new topic node
    new_node = {
        "node_id": new_id(),
        "title":   topic,
        "summary": f"IIT Jammu {topic} information.",
        "text":    f"Category: {topic}.",
        "nodes":   [],
    }
    root_nodes.append(new_node)
    return new_node


# ══════════════════════════════════════════════════════════════════
#  Build nodes from MD files
# ══════════════════════════════════════════════════════════════════

def build_crawled_nodes(
    seed_titles: Set[str],
    existing_fps: Set[str] = None,
    existing_sources: Set[str] = None,
) -> Dict[str, List[Dict]]:

    if existing_fps is None:
        existing_fps = set()
    if existing_sources is None:
        existing_sources = set()

    md_files = sorted(
        [f for f in RAW_DIR.glob("*.md") if not f.name.startswith("_")],
        key=lambda f: f.stat().st_size,
        reverse=True,
    )
    logger.info(f"  Found {len(md_files)} MD files in {RAW_DIR}")

    by_topic: Dict[str, List[Dict]] = defaultdict(list)
    seen_fps: Set[str] = set(existing_fps)
    processed = skipped = new_files = 0

    for fpath in md_files:
        # Skip files already indexed
        if fpath.name in existing_sources:
            skipped += 1
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"  Could not read {fpath.name}: {e}")
            continue

        if len(content.strip()) < 150:
            skipped += 1
            continue

        fp = content_fingerprint(content)
        if fp in seen_fps:
            skipped += 1
            continue
        seen_fps.add(fp)

        topic = assign_topic(fpath.stem, content)
        title = page_title(content)
        sections = extract_sections(content)

        if not sections:
            clean = clean_markdown("\n".join(content.split("\n")[4:]))[:MAX_TEXT_CHARS]
            if len(clean) < MIN_NODE_CHARS:
                skipped += 1
                continue
            if title in seed_titles:
                skipped += 1
                continue
            node = {
                "node_id": new_id(),
                "title":   title,
                "summary": offline_summarize(title, clean),
                "text":    clean,
                "source":  fpath.name,
                "nodes":   [],
            }
            by_topic[topic].append(node)
            processed += 1
            new_files += 1
            continue

        page_node = {
            "node_id": new_id(),
            "title":   title,
            "summary": offline_summarize(title, sections[0]["text"] if sections else ""),
            "text":    "",
            "source":  fpath.name,
            "nodes":   [],
        }
        stack = []
        for sec in sections:
            node = {
                "node_id": new_id(),
                "title":   sec["title"],
                "summary": offline_summarize(sec["title"], sec["text"]),
                "text":    sec["text"],
                "nodes":   [],
            }
            while stack and stack[-1][0] >= sec["level"]:
                stack.pop()
            if stack:
                stack[-1][1].append(node)
            else:
                page_node["nodes"].append(node)
            stack.append((sec["level"], node["nodes"]))

        total_text = sum(len(n["text"]) for n in page_node["nodes"])
        if total_text < MIN_NODE_CHARS:
            skipped += 1
            continue

        by_topic[topic].append(page_node)
        processed += 1
        new_files += 1

    logger.info(f"  Processed: {processed} files, Skipped (already indexed/empty): {skipped}")
    logger.info(f"  🆕 New files added: {new_files}")
    return dict(by_topic)


def build_seed_nodes_map() -> Dict[str, List[Dict]]:
    by_topic: Dict[str, List[Dict]] = defaultdict(list)
    for seed in SEED_NODES:
        node = {
            "node_id": new_id(),
            "title":   seed["title"],
            "summary": offline_summarize(seed["title"], seed["text"]),
            "text":    seed["text"],
            "source":  "hardcoded_seed",
            "nodes":   [],
        }
        by_topic[seed["topic"]].append(node)
    return dict(by_topic)


# ══════════════════════════════════════════════════════════════════
#  Build from scratch (original behavior)
# ══════════════════════════════════════════════════════════════════

def build_tree_fresh() -> Dict:
    logger.info("🌲 Building index tree from scratch...")
    logger.info("  Phase 1: Loading seed nodes...")
    seed_nodes_by_topic = build_seed_nodes_map()
    seed_titles = {n["title"] for nodes in seed_nodes_by_topic.values() for n in nodes}

    logger.info("  Phase 2: Processing crawled files...")
    crawled_nodes_by_topic = build_crawled_nodes(seed_titles)

    logger.info("  Phase 3: Building tree...")
    root_nodes = []
    for topic in TOPIC_ORDER:
        seed_nodes    = seed_nodes_by_topic.get(topic, [])
        crawled_nodes = crawled_nodes_by_topic.get(topic, [])
        if not seed_nodes and not crawled_nodes:
            continue
        all_children = seed_nodes + crawled_nodes
        child_titles = [n["title"] for n in all_children[:4]]
        topic_node = {
            "node_id": new_id(),
            "title":   topic,
            "summary": f"IIT Jammu {topic}. Covers: {', '.join(child_titles[:3])}. {len(all_children)} sub-sections.",
            "text":    f"Category: {topic}. Contains {len(all_children)} pages.",
            "nodes":   all_children,
        }
        root_nodes.append(topic_node)
        logger.info(f"  {topic:40s}: {len(seed_nodes)} seeds + {len(crawled_nodes)} crawled = {len(all_children)} total")

    total = count_nodes(root_nodes)
    return {
        "doc_name":        "IIT Jammu Official Website — Complete Knowledge Base",
        "doc_description": "Complete knowledge base for IIT Jammu. Covers programs, admissions, fees, scholarships, faculty, research, campus, placements, contacts, and all departments.",
        "source_url":   BASE_URL,
        "last_updated": datetime.now().isoformat()[:10],
        "total_nodes":  total,
        "structure":    root_nodes,
    }


# ══════════════════════════════════════════════════════════════════
#  ★ NEW: Merge mode — add only NEW pages to existing index
# ══════════════════════════════════════════════════════════════════

def build_tree_merge() -> Dict:
    logger.info("🌲 MERGE MODE: Adding new pages to existing index...")

    # Load existing index
    existing = load_existing_index()
    if not existing:
        logger.warning("  No existing index found — falling back to fresh build.")
        return build_tree_fresh()

    root_nodes = existing.get("structure", [])
    old_total  = existing.get("total_nodes", 0)

    # Extract what's already indexed
    existing_fps     = set()
    existing_sources = set()
    for topic_node in root_nodes:
        extract_existing_fingerprints(topic_node.get("nodes", []), existing_fps)
        extract_existing_sources(topic_node.get("nodes", []), existing_sources)
    logger.info(f"  Existing sources: {len(existing_sources)} files already indexed")

    # Build new nodes only from NEW md files
    seed_titles = {seed["title"] for seed in SEED_NODES}
    new_nodes_by_topic = build_crawled_nodes(
        seed_titles,
        existing_fps=existing_fps,
        existing_sources=existing_sources,
    )

    # Merge new nodes into existing topic nodes
    total_added = 0
    for topic, new_nodes in new_nodes_by_topic.items():
        if not new_nodes:
            continue
        topic_node = get_or_create_topic_node(root_nodes, topic)
        topic_node["nodes"].extend(new_nodes)
        total_added += len(new_nodes)
        logger.info(f"  ✅ {topic}: +{len(new_nodes)} new nodes added")

    # Reorder root_nodes to match TOPIC_ORDER
    order_map = {t: i for i, t in enumerate(TOPIC_ORDER)}
    root_nodes.sort(key=lambda n: order_map.get(n.get("title",""), 999))

    # Recount total
    new_total = count_nodes(root_nodes)
    logger.info(f"\n  📊 Nodes before: {old_total} → after: {new_total} (+{new_total - old_total})")

    return {
        "doc_name":        existing.get("doc_name", "IIT Jammu Official Website — Complete Knowledge Base"),
        "doc_description": existing.get("doc_description", ""),
        "source_url":      BASE_URL,
        "last_updated":    datetime.now().isoformat()[:10],
        "total_nodes":     new_total,
        "structure":       root_nodes,
    }


# ══════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════

def run_indexer(dry_run=False, show_stats=False, merge=False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("🌲 IIT Jammu Index Builder")
    logger.info(f"   Mode      : {'MERGE' if merge else 'FRESH BUILD'}")
    logger.info(f"   Raw data  : {RAW_DIR}")
    logger.info(f"   Output    : {INDEX_FILE}")

    md_count = len([f for f in RAW_DIR.glob("*.md") if not f.name.startswith("_")])
    logger.info(f"   MD files  : {md_count}")

    # Auto-backup before any write
    if not dry_run and INDEX_FILE.exists():
        backup = INDEX_FILE.with_suffix(".backup.json")
        backup.write_bytes(INDEX_FILE.read_bytes())
        logger.info(f"   Backup    : {backup}")

    tree = build_tree_merge() if merge else build_tree_fresh()

    if show_stats:
        logger.info("\n📊 Index Statistics:")
        for section in tree["structure"]:
            logger.info(f"  {section['title']:40s}: {count_nodes(section['nodes'])} total nodes")
        logger.info(f"\n  TOTAL NODES: {tree['total_nodes']}")
        return

    if not dry_run:
        INDEX_FILE.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
        size_kb = INDEX_FILE.stat().st_size // 1024
        logger.info(f"\n✅ Index written: {INDEX_FILE} ({size_kb} KB)")

    logger.info(f"\n📊 Summary:")
    logger.info(f"   Root sections : {len(tree['structure'])}")
    logger.info(f"   Total nodes   : {tree['total_nodes']}")
    for section in tree["structure"]:
        logger.info(f"   {section['title']:40s}: {len(section['nodes'])} children")

    return tree


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="IIT Jammu Index Builder")
    p.add_argument("--dry-run", action="store_true", help="Build but don't save")
    p.add_argument("--stats",   action="store_true", help="Show stats only")
    p.add_argument("--merge",   action="store_true", help="Merge new pages into existing index (RECOMMENDED)")
    args = p.parse_args()
    run_indexer(dry_run=args.dry_run, show_stats=args.stats, merge=args.merge)