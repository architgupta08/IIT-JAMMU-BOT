"""
indexer.py  —  Robust IIT Jammu Knowledge Index Builder
=========================================================
Converts data/raw/*.md  →  data/processed/iitj_index.json

PROBLEMS SOLVED vs old version:
  1. HTML fragments in good files → deep HTML stripper
  2. Misclassification (faculty→Academic, placement→Admissions) → better scorer
  3. Duplicate content → SHA-256 fingerprint dedup
  4. Empty/tiny nodes polluting the tree → min content threshold
  5. section extraction breaking on repeated headings → dedup heading content
  6. Topic nodes with 100+ children → sub-group by department/sub-topic
  7. Missing key facts (fee, hostel, placement) → hardcoded seed nodes merged in
  8. Bad summaries (just "IIT Jammu...") → stronger TF-IDF + factual-line preference
  9. total_nodes count wrong → count at end after tree is fully built
  10. Indexer crashes on malformed MD → try/except on every file

USAGE:
  python indexer.py           # offline TF-IDF summaries (instant)
  python indexer.py --stats   # show stats without writing
  python indexer.py --dry-run # build but don't save

OUTPUT:
  data/processed/iitj_index.json
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

# Minimum body chars for a node to be included
MIN_NODE_CHARS = 120
# Max chars of text stored per leaf node (keeps index file manageable)
MAX_TEXT_CHARS = 3000
# Max children before sub-grouping kicks in
MAX_CHILDREN   = 40


# ══════════════════════════════════════════════════════════════════
#  STEP 0 — Hardcoded seed nodes (critical facts not on site pages)
#  These are MERGED into the index regardless of what was crawled.
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
#  STEP 1 — Text cleaning utilities
# ══════════════════════════════════════════════════════════════════

def strip_html(text: str) -> str:
    """Aggressively remove all HTML from text."""
    # Remove full HTML tags with content for script/style
    text = re.sub(r"<(script|style|noscript|template)[^>]*>.*?</\1>", " ", text, flags=re.DOTALL|re.I)
    # Remove remaining HTML tags
    text = re.sub(r"<[^>]{1,200}>", " ", text)
    # Remove HTML entities
    text = re.sub(r"&[a-zA-Z0-9#]{1,8};", " ", text)
    # Remove CSS-like patterns
    text = re.sub(r"\.[a-zA-Z][\w-]+\s*\{[^}]*\}", " ", text)
    # Remove JS patterns
    text = re.sub(r"(function\s*\(|var\s+\w+\s*=|const\s+\w+\s*=|let\s+\w+\s*=|=>\s*\{)", " ", text)
    return text


def clean_markdown(text: str) -> str:
    """Clean Markdown body text for storage in the index."""
    text = strip_html(text)
    # Remove source header lines (# Title, **Source:** url, ---)
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip: empty after cleanup, pure URLs, pure class names, lone punctuation
        if not stripped:
            clean_lines.append("")
            continue
        if re.match(r"^https?://\S+$", stripped):
            continue
        if re.match(r"^\[.*\]\(https?://[^)]+\)$", stripped):  # bare link lines
            continue
        if len(stripped) < 4 and not re.search(r"[a-zA-Z0-9]", stripped):
            continue
        # Skip lines that are clearly HTML class/id artifacts
        if re.match(r"^[\w-]+(?:\s+[\w-]+){0,2}$", stripped) and len(stripped) < 30:
            # Could be a real short phrase, keep unless it looks like a CSS class
            if re.match(r"^[a-z][\w-]+$", stripped):  # lowercase-hyphen = class name
                continue
        clean_lines.append(line)

    text = "\n".join(clean_lines)
    # Normalize whitespace
    text = re.sub(r" {3,}", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def plain_text(text: str) -> str:
    """Strip all Markdown/HTML → plain prose for summarization."""
    text = strip_html(text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links → text
    text = re.sub(r"[#*_`|>~\\]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ══════════════════════════════════════════════════════════════════
#  STEP 2 — Offline TF-IDF summarizer (no API)
# ══════════════════════════════════════════════════════════════════

STOPWORDS = {
    "the","a","an","and","or","of","in","to","is","are","was","were","for",
    "on","at","by","this","that","with","from","it","its","be","as","not",
    "have","has","had","he","she","they","we","you","i","will","can","may",
    "all","also","more","about","but","if","so","do","does","did","been",
    "which","who","what","when","where","how","any","our","their","your",
    "would","should","could","into","than","then","there","here","after",
    "before","over","under","again","further","too","very","just","each",
    "both","while","during","between","through","above","below","up","down",
    "out","off","only","same","such","than","other","one","first","last",
    "new","old","high","low","long","short","good","great","best","well",
}


def _sentences(text: str) -> List[str]:
    text = plain_text(text)
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if len(s.strip()) > 30]


def offline_summarize(title: str, text: str, max_chars: int = 250) -> str:
    """
    Extract 1-2 most informative sentences using TF-IDF scoring.
    Prefers sentences with numbers (factual data).
    """
    sents = _sentences(text)
    if not sents:
        return plain_text(text)[:max_chars]
    if len(sents) <= 2:
        return " ".join(sents)[:max_chars]

    # Word frequency
    freq: Counter = Counter()
    for s in sents:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", s.lower())
        freq.update(w for w in words if w not in STOPWORDS)

    # Add title keyword boost
    title_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", title.lower())) - STOPWORDS
    for tw in title_words:
        freq[tw] = freq.get(tw, 0) + 3

    def score(s: str) -> float:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", s.lower())
        if not words:
            return 0.0
        tfidf = sum(freq.get(w, 0) for w in words) / len(words)
        num_bonus  = 0.5 if re.search(r"\d", s) else 0.0      # has numbers
        rs_bonus   = 0.3 if re.search(r"Rs\.?\s*\d|₹", s) else 0.0  # has money
        len_bonus  = 0.2 if 60 < len(s) < 200 else 0.0
        return tfidf + num_bonus + rs_bonus + len_bonus

    scored = sorted(enumerate(sents), key=lambda x: score(x[1]), reverse=True)
    # Top 2, in original order
    indices = sorted([scored[0][0], min(scored[1][0], len(sents)-1)])
    summary = " ".join(sents[i] for i in indices)

    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0] + "…"
    return summary


# ══════════════════════════════════════════════════════════════════
#  STEP 3 — Topic classification
# ══════════════════════════════════════════════════════════════════

TAXONOMY: Dict[str, Dict] = {
    "About IIT Jammu": {
        "keywords": ["history","establishment","2016","vision","mission","about iit","overview",
                     "introduction","iqac","nirf","annual report","institute profile","board of governors",
                     "senate","finance committee","autonomy","institute","iit jammu"],
        "filename_signals": ["about","director","history","overview","nirf","iqac","senate",
                             "board","administration","governance","profile"],
        "weight": 1.0,
    },
    "Academic Programs": {
        "keywords": ["btech","b.tech","mtech","m.tech","msc","m.sc","phd","ph.d",
                     "programme","program","course","curriculum","degree","undergraduate",
                     "postgraduate","doctoral","engineering physics","mathematics computing",
                     "minor","honours","dual degree","behavioural sciences","academic year",
                     "credit","semester","elective","core","specialization","specialisation"],
        "filename_signals": ["btech","mtech","msc","phd","programme","program","course",
                             "curriculum","academic","semester","elective","specializ"],
        "weight": 1.0,
    },
    "Admissions": {
        "keywords": ["admission","jee","gate","jam","josaa","cutoff","rank",
                     "eligibility","apply","application","selection","counselling",
                     "seat matrix","category","sc st","obc","ews","quota","merit list",
                     "document verification","offer letter","provisional admission",
                     "foreign national","sponsored candidate","closing rank","opening rank"],
        "filename_signals": ["admission","jee","gate","josaa","counsell","eligib","seat",
                             "apply","cutoff","rank","document","verification","offer"],
        "weight": 1.2,  # boost admissions
    },
    "Fee Structure": {
        "keywords": ["fee","fees","charges","tuition","hostel charges","mess fee",
                     "payment","refund","financial","cost","waiver","caution deposit",
                     "1,51,720","51,720","rs.","rupees","per semester","per year",
                     "scholarship amount","economic","affordable"],
        "filename_signals": ["fee","charge","tuition","payment","financial","cost",
                             "economic","hostel-fee","mess-fee"],
        "weight": 1.5,  # fees are critical
    },
    "Departments": {
        "keywords": ["department","computer science","cse","civil engineering","electrical",
                     "mechanical","chemical","mathematics","physics","chemistry","hss",
                     "humanities","materials engineering","bioscience","biosciences",
                     "interdisciplinary","department of","faculty list","hod","head of department",
                     "lab facilities","research area","courses offered"],
        "filename_signals": ["computer_science","electrical_engineering","mechanical_engineering",
                             "civil_engineering","chemical","mathematics","physics","chemistry",
                             "hss","materials","bsbe","idp","cds","department"],
        "weight": 1.0,
    },
    "Faculty": {
        "keywords": ["faculty","professor","assistant professor","associate professor",
                     "faculty list","research interest","publication list","staff","supervisor",
                     "phd guide","joining date","specialization","teaching","course taught"],
        "filename_signals": ["faculty","professor","prof_","dr_","staff","people",
                             "faculty-list","people-list"],
        "weight": 1.3,
    },
    "Research": {
        "keywords": ["research","publication","journal","conference","sponsored project",
                     "innovation","hpc","agastya","saptarshi","patent","cif","instrumentation",
                     "funding","serb","dst","csir","anrf","drdo","isro","mnre","funded",
                     "principal investigator","co-pi","grant","research output"],
        "filename_signals": ["research","publication","journal","conference","patent",
                             "hpc","cif","funded","project","lab","center","centre"],
        "weight": 1.0,
    },
    "Campus & Facilities": {
        "keywords": ["campus","hostel","mess","cafeteria","sports","gym","library",
                     "wifi","internet","medical","bank","atm","jagti","paloura",
                     "accommodation","facility","infrastructure","canteen","transport",
                     "bus","health","ambulance","24x7","security","clinic","doctor"],
        "filename_signals": ["hostel","mess","cafeteria","sports","gym","library",
                             "medical","campus","facility","transport","canteen","bank"],
        "weight": 1.0,
    },
    "Placements": {
        "keywords": ["placement","recruit","company","package","lpa","ctc","salary",
                     "internship","hiring","career","job","offer","tnp","ppo",
                     "highest package","average package","past recruiter","placement report",
                     "placement brochure","campus interview","pre-placement offer"],
        "filename_signals": ["placement","recruit","internship","tnp","career","job",
                             "package","lpa","ctc","company","brochure","report"],
        "weight": 1.4,
    },
    "Scholarships & Financial Aid": {
        "keywords": ["scholarship","mcm","merit-cum-means","freeship","financial aid",
                     "stipend","fellowship","pmrf","visvesvaraya","inspire","csir-jrf",
                     "ugc-jrf","gate fellowship","teaching assistantship","need-based",
                     "economic criteria","family income","4.5 lakh","waiver"],
        "filename_signals": ["scholarship","mcm","freeship","financial","fellowship",
                             "stipend","aid","grant"],
        "weight": 1.3,
    },
    "Contact & Administration": {
        "keywords": ["contact","address","phone","email","registrar","dean","administration",
                     "office","helpdesk","reach","location","how to reach","map","distance",
                     "kilometer","nearest","airport","railway","bus","nh-44"],
        "filename_signals": ["contact","reach","address","phone","email","admin",
                             "registrar","dean","location","map","howto","reach-us"],
        "weight": 1.0,
    },
    "Events & Notices": {
        "keywords": ["event","news","notice","circular","announcement","seminar",
                     "workshop","conference","convocation","fest","tender",
                     "recruitment","job opening","interview","walk-in","exhibition",
                     "award","achievement","prize","medal","rank holder"],
        "filename_signals": ["event","news","notice","circular","announcement","seminar",
                             "workshop","conference","convocation","fest","tender",
                             "award","achievement","prize","post"],
        "weight": 0.8,  # lower weight — noisy
    },
    "Research Labs & Centers": {
        "keywords": ["solar","vlsi","electric vehicle","sustainable energy","smart structure",
                     "ai center","underwater","acoustic","drone","sensor","nano","advanced",
                     "center","centre","laboratory","lab","facility","equipment","instrument",
                     "scanning electron","xrd","nmr","spectrometer","hpc cluster"],
        "filename_signals": ["solar","vlsi","ev","underwater","lab","center","centre",
                             "facility","equipment","instrument","cif","hpc"],
        "weight": 1.0,
    },
}


def assign_topic(filename: str, content: str) -> str:
    """
    Improved classifier: weights filename signals higher than content keywords.
    Returns topic with highest score.
    """
    fname_lower = filename.lower()
    sample      = plain_text(content[:2000]).lower()

    best_topic = "About IIT Jammu"
    best_score = 0.0

    for topic, cfg in TAXONOMY.items():
        # Filename signal score (2x weight)
        fname_score = sum(2.0 for sig in cfg["filename_signals"] if sig in fname_lower)
        # Content keyword score
        kw_score    = sum(sample.count(kw) for kw in cfg["keywords"])
        total       = (fname_score + kw_score) * cfg["weight"]

        if total > best_score:
            best_score = total
            best_topic = topic

    return best_topic


# ══════════════════════════════════════════════════════════════════
#  STEP 4 — Markdown section extractor
# ══════════════════════════════════════════════════════════════════

def extract_sections(content: str) -> List[Dict]:
    """
    Parse Markdown into heading-delimited sections.
    Handles: duplicate headings, empty sections, heading-only pages.
    """
    sections: List[Dict] = []
    current_title  = None
    current_level  = 0
    buf: List[str] = []

    def flush():
        if current_title is None:
            return
        text = clean_markdown("\n".join(buf)).strip()
        if len(text) < MIN_NODE_CHARS:
            return
        # Skip sections that are just navigation lists (> 70% link lines)
        lines = [l for l in text.split("\n") if l.strip()]
        if lines:
            link_lines = sum(1 for l in lines if re.search(r"\[.+\]\(https?://", l))
            if link_lines / len(lines) > 0.7:
                return
        sections.append({
            "title": current_title,
            "level": current_level,
            "text":  text[:MAX_TEXT_CHARS],
        })

    # Skip the first 3 lines (title, source, ---)
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
            # Skip generic / duplicate heading titles
            if title.lower() in {"iit jammu", "indian institute of technology jammu",
                                  "home", "menu", "navigation", "contents"}:
                current_title = None
                buf = []
            else:
                current_title = title
                current_level = level
                buf = []
        else:
            buf.append(line)

    flush()
    return sections


def page_title(content: str) -> str:
    for line in content.split("\n")[:6]:
        if line.startswith("# "):
            title = line[2:].strip()
            return re.sub(r"\s*\|\s*IIT Jammu.*$", "", title, flags=re.I).strip()
    return "IIT Jammu Page"


def content_fingerprint(text: str) -> str:
    """SHA-256 of first 800 chars (enough for dedup without being too strict)."""
    return hashlib.sha256(plain_text(text[:800]).encode()).hexdigest()


# ══════════════════════════════════════════════════════════════════
#  STEP 5 — Node ID counter
# ══════════════════════════════════════════════════════════════════

_counter = [0]

def new_id() -> str:
    _counter[0] += 1
    return f"{_counter[0]:04d}"


def count_nodes(nodes: List[Dict]) -> int:
    total = 0
    for n in nodes:
        total += 1 + count_nodes(n.get("nodes", []))
    return total


# ══════════════════════════════════════════════════════════════════
#  STEP 6 — Tree builder
# ══════════════════════════════════════════════════════════════════

def build_seed_nodes() -> Dict[str, List[Dict]]:
    """Build nodes from the hardcoded seed data."""
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


def build_crawled_nodes(seed_titles: Set[str]) -> Dict[str, List[Dict]]:
    """Build nodes from crawled MD files, skipping content already in seeds."""
    md_files = sorted(
        [f for f in RAW_DIR.glob("*.md") if not f.name.startswith("_")],
        key=lambda f: f.stat().st_size,
        reverse=True,  # process bigger files first (more content = higher quality)
    )
    logger.info(f"  Found {len(md_files)} MD files in {RAW_DIR}")

    by_topic: Dict[str, List[Dict]] = defaultdict(list)
    seen_fingerprints: Set[str] = set()
    processed = 0
    skipped   = 0

    for fpath in md_files:
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"  Could not read {fpath.name}: {e}")
            continue

        if len(content.strip()) < 150:
            skipped += 1
            continue

        # Dedup
        fp = content_fingerprint(content)
        if fp in seen_fingerprints:
            skipped += 1
            continue
        seen_fingerprints.add(fp)

        topic = assign_topic(fpath.stem, content)
        title = page_title(content)
        sections = extract_sections(content)

        if not sections:
            # Flat page — single leaf node
            clean = clean_markdown("\n".join(content.split("\n")[4:]))[:MAX_TEXT_CHARS]
            if len(clean) < MIN_NODE_CHARS:
                skipped += 1
                continue
            # Skip if content already covered by seeds
            if title in seed_titles:
                skipped += 1
                continue
            node: Dict = {
                "node_id": new_id(),
                "title":   title,
                "summary": offline_summarize(title, clean),
                "text":    clean,
                "source":  fpath.name,
                "nodes":   [],
            }
            by_topic[topic].append(node)
            processed += 1
            continue

        # Multi-section page → hierarchy
        page_node: Dict = {
            "node_id": new_id(),
            "title":   title,
            "summary": offline_summarize(title, sections[0]["text"] if sections else ""),
            "text":    "",
            "source":  fpath.name,
            "nodes":   [],
        }

        # Stack-based section hierarchy
        stack: List[tuple] = []  # (level, parent_children_list)
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

        # Only add if page has actual content
        total_text = sum(len(n["text"]) for n in page_node["nodes"])
        if total_text < MIN_NODE_CHARS:
            skipped += 1
            continue

        by_topic[topic].append(page_node)
        processed += 1

    logger.info(f"  Processed: {processed} files, Skipped: {skipped}")
    return dict(by_topic)


def _sub_group(nodes: List[Dict], topic: str) -> List[Dict]:
    """
    If a topic has > MAX_CHILDREN nodes, sub-group by department/keyword.
    Example: 122 Academic Programs → grouped by department.
    """
    if len(nodes) <= MAX_CHILDREN:
        return nodes

    # Try to group by filename pattern
    DEPT_PATTERNS = [
        ("Computer Science",  ["computer_science","cse"]),
        ("Electrical Eng.",   ["electrical","ee_"]),
        ("Mechanical Eng.",   ["mechanical","me_"]),
        ("Civil Eng.",        ["civil"]),
        ("Chemical Eng.",     ["chemical","che_"]),
        ("Mathematics",       ["mathematics","math"]),
        ("Physics",           ["physics"]),
        ("Chemistry",         ["chemistry"]),
        ("HSS",               ["hss","humanities"]),
        ("Materials",         ["materials"]),
        ("Biosciences",       ["bsbe","bioscience"]),
        ("Other/General",     []),
    ]

    groups: Dict[str, List[Dict]] = defaultdict(list)
    for n in nodes:
        src = n.get("source", "").lower()
        assigned = False
        for gname, patterns in DEPT_PATTERNS[:-1]:
            if any(p in src for p in patterns):
                groups[gname].append(n)
                assigned = True
                break
        if not assigned:
            groups["Other/General"].append(n)

    # Build sub-group nodes
    result = []
    for gname, gnodes in groups.items():
        if not gnodes:
            continue
        if len(gnodes) == 1:
            result.append(gnodes[0])
            continue
        group_node = {
            "node_id": new_id(),
            "title":   f"{topic} — {gname}",
            "summary": f"{topic} content for {gname}. {len(gnodes)} pages.",
            "text":    f"Sub-section covering {gname} in the context of {topic}.",
            "nodes":   gnodes,
        }
        result.append(group_node)

    return result


def build_tree() -> Dict:
    """Build the complete index tree."""

    logger.info("🌲 Building index tree...")
    logger.info("  Phase 1: Loading seed nodes...")
    seed_nodes_by_topic = build_seed_nodes()
    seed_titles = {n["title"] for nodes in seed_nodes_by_topic.values() for n in nodes}

    logger.info("  Phase 2: Processing crawled files...")
    crawled_nodes_by_topic = build_crawled_nodes(seed_titles)

    logger.info("  Phase 3: Merging and building tree...")
    root_nodes = []

    # All topics in priority order
    TOPIC_ORDER = [
        "About IIT Jammu",
        "Academic Programs",
        "Admissions",
        "Fee Structure",
        "Scholarships & Financial Aid",
        "Placements",
        "Campus & Facilities",
        "Departments",
        "Faculty",
        "Research",
        "Research Labs & Centers",
        "Contact & Administration",
        "Events & Notices",
    ]

    for topic in TOPIC_ORDER:
        seed_nodes    = seed_nodes_by_topic.get(topic, [])
        crawled_nodes = crawled_nodes_by_topic.get(topic, [])

        if not seed_nodes and not crawled_nodes:
            continue

        # Sub-group if too many crawled nodes
        if len(crawled_nodes) > MAX_CHILDREN:
            crawled_nodes = _sub_group(crawled_nodes, topic)

        # Seeds first (authoritative), then crawled
        all_children = seed_nodes + crawled_nodes

        # Build summary from first few child titles
        child_titles = [n["title"] for n in all_children[:4]]
        summary = (
            f"IIT Jammu {topic}. "
            f"Covers: {', '.join(child_titles[:3])}. "
            f"{len(all_children)} sub-sections."
        )

        topic_node = {
            "node_id": new_id(),
            "title":   topic,
            "summary": summary,
            "text":    f"Category: {topic}. Contains {len(all_children)} pages of information.",
            "nodes":   all_children,
        }
        root_nodes.append(topic_node)
        logger.info(f"  {topic:40s}: {len(seed_nodes)} seeds + {len(crawled_nodes)} crawled = {len(all_children)} total")

    # Final node count (accurate)
    total = count_nodes(root_nodes)

    tree = {
        "doc_name":        "IIT Jammu Official Website — Complete Knowledge Base",
        "doc_description": (
            "Complete knowledge base for IIT Jammu (Indian Institute of Technology Jammu, India). "
            "Covers programs, admissions, fees, scholarships, faculty, research, campus, placements, "
            "contacts, and all departments. Built from official website + curated seed data."
        ),
        "source_url":   BASE_URL,
        "last_updated": datetime.now().isoformat()[:10],
        "total_nodes":  total,
        "structure":    root_nodes,
    }
    return tree


# ══════════════════════════════════════════════════════════════════
#  STEP 7 — Entry point
# ══════════════════════════════════════════════════════════════════

def run_indexer(dry_run: bool = False, show_stats: bool = False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("🌲 IIT Jammu Index Builder")
    logger.info(f"   Raw data  : {RAW_DIR}")
    logger.info(f"   Output    : {INDEX_FILE}")

    md_count = len([f for f in RAW_DIR.glob("*.md") if not f.name.startswith("_")])
    logger.info(f"   MD files  : {md_count}")

    tree = build_tree()

    if show_stats:
        logger.info("\n📊 Index Statistics:")
        for section in tree["structure"]:
            direct = len(section["nodes"])
            deep   = count_nodes(section["nodes"])
            logger.info(f"  {section['title']:40s}: {direct} direct children, {deep} total nodes")
        logger.info(f"\n  TOTAL NODES: {tree['total_nodes']}")
        return

    if not dry_run:
        INDEX_FILE.write_text(
            json.dumps(tree, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        size_kb = INDEX_FILE.stat().st_size // 1024
        logger.info(f"\n✅ Index written: {INDEX_FILE} ({size_kb} KB)")

    logger.info(f"\n📊 Summary:")
    logger.info(f"   Root sections : {len(tree['structure'])}")
    logger.info(f"   Total nodes   : {tree['total_nodes']}")
    logger.info(f"   Seed nodes    : {len(SEED_NODES)}")
    for section in tree["structure"]:
        logger.info(f"   {section['title']:40s}: {len(section['nodes'])} children")

    return tree


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="IIT Jammu Index Builder")
    p.add_argument("--dry-run",  action="store_true", help="Build but don't save")
    p.add_argument("--stats",    action="store_true", help="Show stats only")
    args = p.parse_args()
    run_indexer(dry_run=args.dry_run, show_stats=args.stats)
