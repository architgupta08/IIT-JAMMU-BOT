"""
response_enhancer.py — Enrich chatbot responses with related suggestions,
professional footers, and readability improvements.

Used by main.py after the RAG engine produces a raw answer.
"""
import os
import logging
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────
ENABLE_SUGGESTIONS: bool = os.getenv("ENABLE_SUGGESTIONS", "true").lower() == "true"
ENABLE_FOOTER:      bool = os.getenv("ENABLE_FOOTER",      "true").lower() == "true"
MAX_SUGGESTIONS:    int  = int(os.getenv("MAX_SUGGESTIONS", "3"))

# ── Topic → related questions mapping ────────────────────────────
# Each entry maps a set of trigger keywords to a list of follow-up questions.
_TOPIC_SUGGESTIONS = [
    (
        {"fee", "fees", "tuition", "cost", "expense"},
        [
            "Are there any scholarships available at IIT Jammu?",
            "What is the hostel fee at IIT Jammu?",
            "How can I pay the semester fee online?",
        ],
    ),
    (
        {"btech", "b.tech", "undergraduate", "ug", "jee", "josaa"},
        [
            "What is the B.Tech fee structure at IIT Jammu?",
            "Which departments offer B.Tech programs?",
            "What is the JEE Advanced cutoff for IIT Jammu?",
        ],
    ),
    (
        {"mtech", "m.tech", "gate", "postgraduate", "pg"},
        [
            "What are the GATE cutoffs for M.Tech admission at IIT Jammu?",
            "What is the M.Tech fee structure?",
            "Is there a stipend for M.Tech students at IIT Jammu?",
        ],
    ),
    (
        {"phd", "ph.d", "doctorate", "research", "fellowship", "pmrf"},
        [
            "What is the PhD stipend at IIT Jammu?",
            "How to apply for PhD at IIT Jammu?",
            "What research facilities are available at IIT Jammu?",
        ],
    ),
    (
        {"hostel", "mess", "accommodation", "room", "dormitory"},
        [
            "What are the hostel facilities at IIT Jammu?",
            "What is the mess fee per semester?",
            "Are hostels available for all students at IIT Jammu?",
        ],
    ),
    (
        {"placement", "job", "recruit", "lpa", "ctc", "internship", "tnp"},
        [
            "What are the top recruiters at IIT Jammu?",
            "What is the average placement package at IIT Jammu?",
            "How can I register with the Training and Placement Cell?",
        ],
    ),
    (
        {"faculty", "professor", "department", "cse", "ee", "me", "ce", "che"},
        [
            "Who is the director of IIT Jammu?",
            "How many faculty members are in the CSE department?",
            "What research areas do IIT Jammu faculty work on?",
        ],
    ),
    (
        {"scholarship", "mcm", "merit", "financial", "aid"},
        [
            "How to apply for MCM scholarship at IIT Jammu?",
            "What is the income limit for need-based scholarships?",
            "Are there merit-based scholarships for B.Tech students?",
        ],
    ),
    (
        {"admission", "apply", "application", "eligibility", "cutoff"},
        [
            "What documents are required for IIT Jammu admission?",
            "What is the admission process for B.Tech at IIT Jammu?",
            "When does the IIT Jammu admission portal open?",
        ],
    ),
    (
        {"campus", "location", "address", "jagti", "nagrota", "jammu"},
        [
            "How to reach IIT Jammu campus?",
            "What facilities are available at the IIT Jammu permanent campus?",
            "What is the nearest railway station to IIT Jammu?",
        ],
    ),
]


def _extract_keywords(text: str) -> set:
    """Extract lowercase significant words from text."""
    import re
    stop = {
        "what", "is", "the", "at", "in", "for", "of", "a", "an", "and", "or",
        "tell", "me", "about", "how", "do", "i", "can", "you", "please",
        "are", "there", "any", "which", "does", "give", "list", "show",
    }
    return {
        w.lower()
        for w in re.findall(r"\b\w+\b", text)
        if w.lower() not in stop and len(w) > 2
    }


def get_related_suggestions(query: str, answer: str) -> List[str]:
    """
    Return up to MAX_SUGGESTIONS follow-up questions related to the query/answer.

    Matches trigger keywords against combined query+answer text.
    Returns an empty list if ENABLE_SUGGESTIONS is False.
    """
    if not ENABLE_SUGGESTIONS:
        return []

    combined_keywords = _extract_keywords(query + " " + answer)
    best_match: Optional[List[str]] = None
    best_overlap = 0

    for triggers, questions in _TOPIC_SUGGESTIONS:
        overlap = len(combined_keywords & triggers)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = questions

    if best_match and best_overlap > 0:
        return best_match[:MAX_SUGGESTIONS]
    return []


def build_footer(
    sources,
    confidence: float,
    response_time_ms: Optional[float] = None,
) -> str:
    """
    Build a professional footer string with source citations and timestamp.

    Args:
        sources:         List of SourceNode-like objects with .title and .path.
        confidence:      Confidence score [0, 1].
        response_time_ms: Optional response time in milliseconds.

    Returns:
        A Markdown-formatted footer string, or empty string if disabled.
    """
    if not ENABLE_FOOTER:
        return ""

    lines = ["\n\n---"]

    # Sources — deduplicate by path and list unique titles
    if sources:
        seen_paths: set = set()
        cited = []
        for s in sources[:3]:  # limit to 3 citations
            if s.path not in seen_paths:
                cited.append(s.title)
                seen_paths.add(s.path)
        if cited:
            lines.append("📖 **Sources:** " + " | ".join(f"`{t}`" for t in cited))

    # Confidence badge
    if confidence >= 0.75:
        badge = "🟢 High confidence"
    elif confidence >= 0.50:
        badge = "🟡 Medium confidence"
    else:
        badge = "🔴 Low confidence — please verify at [iitjammu.ac.in](https://www.iitjammu.ac.in)"

    meta_parts = [badge]
    if response_time_ms is not None:
        meta_parts.append(f"⚡ {response_time_ms:.0f} ms")

    lines.append(" · ".join(meta_parts))

    # Timestamp
    ts = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    lines.append(f"🕐 {ts}")

    return "\n".join(lines)
