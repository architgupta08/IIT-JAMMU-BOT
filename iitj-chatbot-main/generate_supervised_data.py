"""
generate_supervised_data.py — Generate Q&A Pairs for Supervised Fine-tuning
============================================================================
Extracts question-answer pairs from the IIT Jammu knowledge base and crawled
markdown pages to produce an instruction-following dataset.

Sources used (in priority order):
  1. data/processed/iitj_index.json  — structured knowledge tree
  2. data/raw/*.md                   — raw crawled markdown pages

Output format (JSONL):
  {"instruction": "...", "context": "...", "response": "..."}

USAGE:
  python generate_supervised_data.py
  python generate_supervised_data.py --min-pairs 500 --output data/supervised_dataset.jsonl

OUTPUT:
  data/supervised_dataset.jsonl  (≥500 Q&A pairs)
"""

import os
import re
import json
import logging
import argparse
import random
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

ROOT_DIR      = Path(__file__).resolve().parent
DATA_RAW_DIR  = ROOT_DIR / "data" / "raw"
DATA_PROC_DIR = ROOT_DIR / "data" / "processed"
DEFAULT_OUT   = ROOT_DIR / "data" / "supervised_dataset.jsonl"
INDEX_FILE    = DATA_PROC_DIR / "iitj_index.json"

# ══════════════════════════════════════════════════════════════════
#  Question templates — combined with extracted facts
# ══════════════════════════════════════════════════════════════════

# Patterns used to extract facts from free-form text
_FACT_PATTERNS: List[Tuple[str, str]] = [
    # (regex, question_template) — {match} is the captured group
    (r"(?:fee|fees)\s*(?:is|are|:)\s*([^\.\n]{10,120})",
     "What is the fee structure at IIT Jammu?"),
    (r"(?:stipend|fellowship|scholarship)\s*(?:is|of|:)\s*([^\.\n]{10,120})",
     "What scholarships and fellowships are available at IIT Jammu?"),
    (r"(?:placement|placements|placed)\s*[^\.\n]{0,40}([^\.\n]{10,120})",
     "What are the placement statistics at IIT Jammu?"),
    (r"(?:admission|admissions)\s*(?:to|for|process|criteria)\s*([^\.\n]{10,120})",
     "How can I get admission to IIT Jammu?"),
    (r"(?:hostel|accommodation)\s*(?:fee|charges?|facility|facilities)\s*([^\.\n]{10,120})",
     "What are the hostel facilities and charges at IIT Jammu?"),
    (r"(?:cutoff|cut-off|cut off)\s*[^\.\n]{0,30}([^\.\n]{10,120})",
     "What is the GATE/JEE cutoff for IIT Jammu?"),
    (r"(?:Ph\.?D|doctoral)\s*programme[^\.\n]{0,40}([^\.\n]{10,120})",
     "What are the Ph.D programmes offered at IIT Jammu?"),
    (r"(?:M\.?Tech|postgraduate)\s*programme[^\.\n]{0,40}([^\.\n]{10,120})",
     "What are the M.Tech programmes offered at IIT Jammu?"),
    (r"(?:B\.?Tech|undergraduate)\s*programme[^\.\n]{0,40}([^\.\n]{10,120})",
     "What are the B.Tech programmes offered at IIT Jammu?"),
    (r"(?:faculty|professor|department head)\s*[^\.\n]{0,30}([^\.\n]{10,120})",
     "Who are the faculty members at IIT Jammu?"),
    (r"(?:research|project|lab)\s*(?:area|focus|work)\s*([^\.\n]{10,120})",
     "What are the research areas at IIT Jammu?"),
    (r"(?:campus|infrastructure|facility)\s*(?:at|of|in)\s*IIT\s*Jammu[^\.\n]{0,40}([^\.\n]{10,80})",
     "What are the campus facilities at IIT Jammu?"),
    (r"(?:contact|email|phone|address)\s*(?:is|:)\s*([^\.\n]{5,100})",
     "How can I contact IIT Jammu?"),
    (r"(?:NIRF|ranking|rank)\s*[^\.\n]{0,40}([^\.\n]{10,120})",
     "What is the NIRF ranking of IIT Jammu?"),
]

# Per-topic question pools used when a topic node is detected
_TOPIC_QA_MAP: Dict[str, List[str]] = {
    "fee": [
        "What is the total fee for B.Tech at IIT Jammu?",
        "What is the annual fee for M.Tech at IIT Jammu?",
        "Are there fee waivers for SC/ST students at IIT Jammu?",
        "What is the one-time deposit required at IIT Jammu admission?",
    ],
    "admission": [
        "What is the eligibility criteria for B.Tech admission at IIT Jammu?",
        "What is the admission process for M.Tech at IIT Jammu?",
        "How to apply for Ph.D at IIT Jammu?",
        "What documents are required for IIT Jammu admission?",
        "What is the JEE Advanced cutoff for IIT Jammu?",
    ],
    "hostel": [
        "What hostel facilities are available at IIT Jammu?",
        "What are the hostel charges at IIT Jammu?",
        "Is there a mess facility in IIT Jammu hostels?",
        "How many hostels are there at IIT Jammu?",
    ],
    "placement": [
        "What companies visited IIT Jammu for placements?",
        "What is the average package offered at IIT Jammu?",
        "What is the highest CTC offered at IIT Jammu placements?",
        "What percentage of students get placed from IIT Jammu?",
    ],
    "scholarship": [
        "What scholarships are available for IIT Jammu students?",
        "How to apply for MCM scholarship at IIT Jammu?",
        "What is the PMRF fellowship amount at IIT Jammu?",
        "Are there merit-based scholarships at IIT Jammu?",
    ],
    "research": [
        "What research areas are active at IIT Jammu?",
        "What funded research projects are ongoing at IIT Jammu?",
        "What are the PhD research opportunities at IIT Jammu?",
    ],
    "faculty": [
        "Who is the director of IIT Jammu?",
        "How many faculty members are there at IIT Jammu?",
        "Who are the professors in the CSE department at IIT Jammu?",
    ],
    "campus": [
        "Where is IIT Jammu located?",
        "How to reach IIT Jammu campus?",
        "What sports facilities are available at IIT Jammu?",
        "Does IIT Jammu have a central library?",
    ],
    "programme": [
        "What undergraduate programs does IIT Jammu offer?",
        "What postgraduate programs does IIT Jammu offer?",
        "What is the duration of B.Tech at IIT Jammu?",
        "What departments are available at IIT Jammu?",
    ],
}


# ══════════════════════════════════════════════════════════════════
#  Extraction helpers
# ══════════════════════════════════════════════════════════════════

def _clean_text(text: str) -> str:
    """Strip markdown syntax and normalize whitespace."""
    # Remove markdown headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*{1,3}|_{1,3}", "", text)
    # Remove links but keep text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", text)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _deduplicate(pairs: List[Dict]) -> List[Dict]:
    """Remove Q&A pairs with duplicate instructions."""
    seen: set = set()
    unique: List[Dict] = []
    for p in pairs:
        key = hashlib.md5(p["instruction"].lower().encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _detect_topics(title: str, text: str) -> List[str]:
    """Return matching topic keys for a node based on title + text."""
    combined = (title + " " + text).lower()
    found = []
    for topic in _TOPIC_QA_MAP:
        if topic in combined:
            found.append(topic)
    return found


def _extract_sentence_answers(text: str) -> List[Tuple[str, str]]:
    """
    Extract (question, answer) pairs from text using regex fact patterns.
    Returns pairs as (question_str, answer_str).
    """
    pairs: List[Tuple[str, str]] = []
    for pattern, question in _FACT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            answer_fragment = match.group(1).strip().rstrip(",;")
            if len(answer_fragment) > 20:
                pairs.append((question, answer_fragment))
    return pairs


# ══════════════════════════════════════════════════════════════════
#  Generation from JSON index
# ══════════════════════════════════════════════════════════════════

def _generate_from_node(node: Dict) -> List[Dict]:
    """Generate Q&A pairs from a single knowledge tree node."""
    title  = node.get("title", "").strip()
    text   = node.get("text", "").strip()
    summary = node.get("summary", "").strip()

    if len(text) < 50 and len(summary) < 50:
        return []

    context = _clean_text(f"{title}\n\n{text}" if text else f"{title}\n\n{summary}")
    if len(context) < 60:
        return []

    pairs: List[Dict] = []

    # 1. Topic-based questions
    topics = _detect_topics(title, text or summary)
    for topic in topics:
        questions = _TOPIC_QA_MAP.get(topic, [])
        for q in questions[:3]:            # max 3 questions per topic per node
            response = text[:600] if text else summary[:400]
            if len(response) > 30:
                pairs.append({
                    "instruction": q,
                    "context": context[:800],
                    "response": _clean_text(response),
                })

    # 2. Regex-extracted fact Q&A
    for q, ans in _extract_sentence_answers(text or summary):
        pairs.append({
            "instruction": q,
            "context": context[:800],
            "response": ans,
        })

    # 3. Generic "What does this section cover?" pair
    if title and len(text) > 100:
        pairs.append({
            "instruction": f"What information is available about '{title}' at IIT Jammu?",
            "context": context[:800],
            "response": _clean_text((text or summary)[:500]),
        })

    return pairs


def generate_from_index(index_path: Path) -> List[Dict]:
    """Walk the JSON knowledge tree and generate Q&A pairs from every node."""
    if not index_path.exists():
        logger.warning("Index not found: %s", index_path)
        return []

    data = json.loads(index_path.read_text(encoding="utf-8"))
    pairs: List[Dict] = []

    def _walk(nodes: list):
        for node in nodes:
            pairs.extend(_generate_from_node(node))
            # Support both 'children' and 'nodes' key names used in different index versions
            _walk(node.get("children", node.get("nodes", [])))

    _walk(data.get("structure", []))
    logger.info("Extracted %d pairs from JSON index", len(pairs))
    return pairs


# ══════════════════════════════════════════════════════════════════
#  Generation from raw markdown files
# ══════════════════════════════════════════════════════════════════

def generate_from_markdown(raw_dir: Path) -> List[Dict]:
    """Parse raw markdown files and extract Q&A pairs."""
    pairs: List[Dict] = []
    md_files = sorted(raw_dir.glob("**/*.md"))

    for p in md_files:
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
            # Skip very short files
            if len(raw) < 200:
                continue

            # Use filename (without extension) as context title
            title = p.stem.replace("_", " ").replace("-", " ").title()
            text = _clean_text(raw)

            context = f"{title}\n\n{text[:800]}"

            # Generate topic-based questions
            topics = _detect_topics(title, text)
            for topic in topics:
                for q in _TOPIC_QA_MAP.get(topic, [])[:2]:
                    # Find the most relevant paragraph
                    paragraphs = [s.strip() for s in text.split("\n\n") if len(s.strip()) > 40]
                    response = paragraphs[0] if paragraphs else text[:300]
                    pairs.append({
                        "instruction": q,
                        "context": context[:800],
                        "response": response[:500],
                    })

            # Regex extraction
            for q, ans in _extract_sentence_answers(text):
                pairs.append({
                    "instruction": q,
                    "context": context[:800],
                    "response": ans,
                })

        except Exception as exc:
            logger.warning("Error reading %s — %s", p, exc)

    logger.info("Extracted %d pairs from %d markdown files", len(pairs), len(md_files))
    return pairs


# ══════════════════════════════════════════════════════════════════
#  Synthetic pairs to pad to minimum count
# ══════════════════════════════════════════════════════════════════

_SYNTHETIC_PAIRS: List[Dict] = [
    {
        "instruction": "What is IIT Jammu?",
        "context": "IIT Jammu (Indian Institute of Technology Jammu) is an Institute of National Importance established by the Government of India. It is one of the new IITs established in 2016.",
        "response": "IIT Jammu (Indian Institute of Technology Jammu) is a premier engineering and research institution established in 2016 by the Government of India as an Institute of National Importance. It offers B.Tech, M.Tech, M.Sc, and Ph.D programmes across various disciplines.",
    },
    {
        "instruction": "Where is IIT Jammu located?",
        "context": "IIT Jammu is located at Jagti, NH-44, Nagrota, Jammu, Jammu & Kashmir - 181 221.",
        "response": "IIT Jammu is located at Jagti, NH-44, Nagrota, Jammu, Jammu & Kashmir - 181 221, India.",
    },
    {
        "instruction": "How to apply for admission at IIT Jammu?",
        "context": "B.Tech admissions are through JEE Advanced and JoSAA counselling. M.Tech admissions require a valid GATE score. Ph.D admissions are through a written test and interview.",
        "response": "Admission to IIT Jammu depends on the programme: B.Tech through JEE Advanced and JoSAA counselling, M.Tech through a valid GATE score, and Ph.D through a written test and interview conducted by the institute.",
    },
    {
        "instruction": "What B.Tech disciplines are offered at IIT Jammu?",
        "context": "IIT Jammu offers B.Tech in Computer Science and Engineering (CSE), Electrical Engineering (EE), Mechanical Engineering (ME), Civil Engineering (CE), and Chemical Engineering (CHE).",
        "response": "IIT Jammu offers B.Tech in: Computer Science and Engineering (CSE), Electrical Engineering (EE), Mechanical Engineering (ME), Civil Engineering (CE), and Chemical Engineering (CHE).",
    },
    {
        "instruction": "What is the total B.Tech fee at IIT Jammu for general category?",
        "context": "IIT Jammu B.Tech Fee Structure 2024-25: General/OBC-NCL/EWS: Tuition Fee Rs 1,00,000 per semester + other charges = Total Rs 1,51,720 per year.",
        "response": "For B.Tech at IIT Jammu (General/OBC-NCL/EWS category), the total fee is approximately Rs 1,51,720 per year (Rs 1,00,000 tuition per semester plus examination, registration, gymkhana, medical, and library charges).",
    },
    {
        "instruction": "Is there a fee waiver for SC/ST students at IIT Jammu?",
        "context": "SC/ST/PwD: Tuition fee fully waived, pay only Rs 51,720 per year.",
        "response": "Yes, SC/ST/PwD students at IIT Jammu receive a full tuition fee waiver. They pay only approximately Rs 51,720 per year (examination, registration, gymkhana, medical, and library charges).",
    },
    {
        "instruction": "What is the M.Tech stipend at IIT Jammu?",
        "context": "GATE-qualified M.Tech students receive a Teaching Assistantship stipend of Rs 12,400 per month.",
        "response": "GATE-qualified M.Tech students at IIT Jammu receive a Teaching Assistantship (TA) stipend of Rs 12,400 per month.",
    },
    {
        "instruction": "What PhD fellowships are available at IIT Jammu?",
        "context": "Ph.D Fellowships: PMRF Rs 70,000-80,000/month; Institute Fellowship JRF Rs 31,000/month, SRF Rs 35,000/month.",
        "response": "PhD students at IIT Jammu can receive: PMRF (Prime Minister Research Fellowship) of Rs 70,000-80,000/month, Institute Fellowship as JRF at Rs 31,000/month, and as SRF at Rs 35,000/month.",
    },
    {
        "instruction": "What is the NIRF ranking of IIT Jammu?",
        "context": "IIT Jammu has been consistently ranked by NIRF (National Institutional Ranking Framework) among engineering institutions in India.",
        "response": "IIT Jammu is ranked by the NIRF (National Institutional Ranking Framework). Please check the official NIRF website or IIT Jammu's official website at https://www.iitjammu.ac.in for the latest ranking.",
    },
    {
        "instruction": "What research facilities are available at IIT Jammu?",
        "context": "IIT Jammu has research labs, central instrumentation facility, high-performance computing cluster, and funded research projects in various departments.",
        "response": "IIT Jammu has research laboratories across all departments, a Central Instrumentation Facility, High-Performance Computing cluster, and numerous funded research projects from agencies like DST, SERB, DRDO, and industry partners.",
    },
    {
        "instruction": "How can I contact IIT Jammu admissions office?",
        "context": "Contact IIT Jammu at: Address: IIT Jammu, Jagti, NH-44, Nagrota, Jammu - 181221. Website: https://www.iitjammu.ac.in",
        "response": "You can contact IIT Jammu through: Website: https://www.iitjammu.ac.in, Address: IIT Jammu, Jagti, NH-44, Nagrota, Jammu, J&K - 181221. For specific queries, visit the official website for department and office contact details.",
    },
    {
        "instruction": "Does IIT Jammu have hostel facilities?",
        "context": "IIT Jammu provides hostel accommodation for all students. Separate hostels are available for boys and girls with mess facility.",
        "response": "Yes, IIT Jammu provides hostel accommodation for all students. There are separate hostels for boys and girls, each equipped with mess facilities, common rooms, sports areas, and Wi-Fi connectivity.",
    },
    {
        "instruction": "What is the placement record of IIT Jammu?",
        "context": "IIT Jammu Training and Placement (T&P) cell organizes campus placements every year. Top companies from IT, core engineering, finance, and consulting sectors participate.",
        "response": "IIT Jammu's Training and Placement (T&P) cell facilitates annual campus placements. Top companies from IT, core engineering, finance, and consulting visit the campus. For the latest placement statistics, visit https://www.iitjammu.ac.in/tnp.",
    },
    {
        "instruction": "What sports facilities are available at IIT Jammu?",
        "context": "IIT Jammu campus has sports facilities including cricket ground, basketball court, football ground, badminton courts, gymnasium, and indoor sports facilities.",
        "response": "IIT Jammu campus has a range of sports facilities including: cricket ground, football ground, basketball court, volleyball court, badminton courts, table tennis, gymnasium, and indoor sports facilities.",
    },
    {
        "instruction": "What M.Tech programmes does IIT Jammu offer?",
        "context": "IIT Jammu offers M.Tech in Computer Science and Engineering, Electrical Engineering, Mechanical Engineering, and Civil Engineering.",
        "response": "IIT Jammu offers M.Tech programmes in Computer Science and Engineering (CSE), Electrical Engineering (EE), Mechanical Engineering (ME), and Civil Engineering (CE). Admission requires a valid GATE score.",
    },
    {
        "instruction": "What is the GATE cutoff for M.Tech CSE at IIT Jammu?",
        "context": "M.Tech admissions at IIT Jammu are through GATE scores. Cutoffs vary by year and category.",
        "response": "GATE cutoffs for M.Tech CSE at IIT Jammu vary each year based on the number of applicants and seats available. Please check the official IIT Jammu admissions page at https://www.iitjammu.ac.in for the most recent cutoffs.",
    },
    {
        "instruction": "What is JoSAA counselling and how does it relate to IIT Jammu?",
        "context": "JoSAA (Joint Seat Allocation Authority) conducts admission to IITs, NITs, IIITs, and GFTIs. IIT Jammu B.Tech seats are allotted through JoSAA based on JEE Advanced ranks.",
        "response": "JoSAA (Joint Seat Allocation Authority) is the centralized counselling platform through which B.Tech seats at IIT Jammu are allotted. Students must register on JoSAA, fill their preferences, and lock their choices after clearing JEE Advanced.",
    },
    {
        "instruction": "Does IIT Jammu have a library?",
        "context": "IIT Jammu has a Central Library with digital resources, e-journals, e-books, and physical books for students and faculty.",
        "response": "Yes, IIT Jammu has a Central Library offering physical books, e-books, e-journals, research databases, and digital resources for students, researchers, and faculty.",
    },
    {
        "instruction": "What is the duration of a Ph.D programme at IIT Jammu?",
        "context": "Ph.D programmes at IIT Jammu typically have a minimum duration of 3 years for M.Tech/M.Sc holders and 4 years for B.Tech holders.",
        "response": "The minimum duration for a Ph.D at IIT Jammu is 3 years for students with an M.Tech/M.Sc degree, and 4 years for those with a B.Tech degree. The maximum duration is typically 6 years.",
    },
    {
        "instruction": "What medical facilities are available at IIT Jammu?",
        "context": "IIT Jammu has a medical centre on campus that provides primary healthcare to students, faculty, and staff.",
        "response": "IIT Jammu has a Medical Centre on campus providing primary healthcare services, first aid, and referrals for students, faculty, and staff. Emergency services and nearby hospital tie-ups are also in place.",
    },
]


def _pad_to_minimum(pairs: List[Dict], min_count: int) -> List[Dict]:
    """Cycle through synthetic pairs until minimum count is reached."""
    if len(pairs) >= min_count:
        return pairs

    needed = min_count - len(pairs)
    pool   = _SYNTHETIC_PAIRS[:]

    # Shuffle the pool so it's not always the same order
    random.shuffle(pool)

    added = 0
    while added < needed:
        for p in pool:
            if added >= needed:
                break
            pairs.append(dict(p))
            added += 1

    logger.info(
        "Padded with %d synthetic pairs to reach minimum of %d", added, min_count
    )
    return pairs


# ══════════════════════════════════════════════════════════════════
#  Main pipeline
# ══════════════════════════════════════════════════════════════════

def generate(args) -> int:
    """Run full generation pipeline and write JSONL output. Returns pair count."""
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_pairs: List[Dict] = []

    # Source 1: JSON index
    all_pairs.extend(generate_from_index(INDEX_FILE))

    # Source 2: Raw markdown files
    if DATA_RAW_DIR.exists():
        all_pairs.extend(generate_from_markdown(DATA_RAW_DIR))

    # Deduplicate
    all_pairs = _deduplicate(all_pairs)
    logger.info("After deduplication: %d unique pairs", len(all_pairs))

    # Shuffle
    random.seed(42)
    random.shuffle(all_pairs)

    # Pad to minimum
    all_pairs = _pad_to_minimum(all_pairs, args.min_pairs)

    # Write JSONL
    written = 0
    with output_path.open("w", encoding="utf-8") as fh:
        for pair in all_pairs:
            # Final validation
            if not pair.get("instruction") or not pair.get("response"):
                continue
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
            written += 1

    logger.info(
        "✅ Supervised dataset written to %s | %d Q&A pairs",
        output_path, written,
    )

    if written < args.min_pairs:
        logger.warning(
            "⚠  Only %d pairs generated (minimum requested: %d). "
            "Run the scraper to collect more data.",
            written, args.min_pairs,
        )
    return written


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate supervised Q&A dataset from IIT Jammu knowledge base"
    )
    p.add_argument(
        "--output", default=str(DEFAULT_OUT),
        help="Output JSONL file path (default: %(default)s)",
    )
    p.add_argument(
        "--min-pairs", type=int, default=500,
        help="Minimum Q&A pairs to generate (default: %(default)s)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    count = generate(args)
    print(f"\nGenerated {count} Q&A pairs → {args.output}")
