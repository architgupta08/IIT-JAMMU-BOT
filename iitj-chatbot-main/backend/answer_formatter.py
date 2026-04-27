"""
answer_formatter.py — Format raw LLM responses into professional chatbot output.

Handles:
  - Normalising Markdown (fix inconsistent bullet symbols, heading levels)
  - Adding section emojis where helpful
  - Cleaning up spacing and excessive blank lines
  - Ensuring a consistent conversational tone footer
  - Language-aware formatting
"""
import re
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────
ENABLE_FORMATTING: bool = os.getenv("ENABLE_ANSWER_FORMATTING", "true").lower() == "true"
MAX_RESPONSE_LENGTH: int = int(os.getenv("MAX_RESPONSE_LENGTH", "2000"))

# ── Keyword → emoji mapping for section headings ─────────────────
_SECTION_EMOJIS = {
    # Fees and finances
    r"\bfee(s)?\b|\btuition\b|\bfinance\b|\bscholarship\b|\bstipend\b|\bmcm\b": "💰",
    # Academics and programs
    r"\bprogram(me)?s?\b|\bcourse(s)?\b|\bdegree(s)?\b|\bcurriculum\b|\bsyllabus\b": "📚",
    r"\bb\.?tech\b|\bm\.?tech\b|\bphd\b|\bph\.d\b|\bm\.?sc\b|\bmba\b": "🎓",
    # Admissions and eligibility
    r"\badmission(s)?\b|\beligibility\b|\bcutoff\b|\bjee\b|\bgate\b|\bjosaa\b": "📝",
    # Campus and facilities
    r"\bhostel(s)?\b|\bmess\b|\bcampus\b|\bfacility\b|\bfacilities\b|\blibrary\b": "🏛️",
    r"\bsport(s)?\b|\bgymnasium\b|\bground\b|\bstadium\b": "⚽",
    # Faculty and departments
    r"\bfaculty\b|\bprofessor\b|\bdepartment(s)?\b|\bstaff\b": "👨‍🏫",
    # Research
    r"\bresearch\b|\bproject(s)?\b|\blab(s)?\b|\blaboratory\b|\bpublication\b": "🔬",
    # Placements
    r"\bplacement(s)?\b|\brecruit(ment)?\b|\bpackage\b|\blpa\b|\bctc\b|\binternship\b": "💼",
    # Contact / location
    r"\bcontact\b|\baddress\b|\blocation\b|\bphone\b|\bemail\b|\bwebsite\b": "📞",
    # Dates and deadlines
    r"\bdeadline(s)?\b|\bdate(s)?\b|\bschedule\b|\bcalendar\b": "📅",
    # Events and activities
    r"\bevent(s)?\b|\bfest\b|\bactivity\b|\bactivities\b|\bclub(s)?\b": "🎉",
}


def _add_section_emoji(line: str) -> str:
    """Prepend an appropriate emoji to a heading line if none is already present."""
    stripped = line.lstrip("#").strip()
    # Skip if line already contains an emoji (rough heuristic: codepoint > 0x2600)
    if any(ord(c) > 0x2600 for c in stripped):
        return line

    for pattern, emoji in _SECTION_EMOJIS.items():
        if re.search(pattern, stripped, re.I):
            # Rebuild with emoji after the heading marker (if any)
            match = re.match(r"^(#{1,4}\s*)(.*)", line)
            if match:
                return f"{match.group(1)}{emoji} {match.group(2).lstrip()}"
            return f"{emoji} {line}"
    return line


def _normalise_bullets(text: str) -> str:
    """Unify different bullet styles (-, *, •) to a consistent bullet (•)."""
    # Only replace at line start to avoid changing inline dashes
    return re.sub(r"(?m)^[ \t]*[-*]\s+", "• ", text)


def _clean_spacing(text: str) -> str:
    """Remove excessive blank lines (max 1 consecutive blank line)."""
    # Replace 3+ consecutive newlines with exactly 2
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _truncate_if_needed(text: str) -> str:
    """Truncate response if it exceeds MAX_RESPONSE_LENGTH characters."""
    if len(text) <= MAX_RESPONSE_LENGTH:
        return text
    truncated = text[:MAX_RESPONSE_LENGTH]
    # Try to end at a sentence boundary
    last_period = max(
        truncated.rfind(". "),
        truncated.rfind(".\n"),
        truncated.rfind("! "),
        truncated.rfind("? "),
    )
    if last_period > MAX_RESPONSE_LENGTH // 2:
        truncated = truncated[: last_period + 1]
    return truncated + "\n\n_[Response truncated. Visit https://www.iitjammu.ac.in for full details.]_"


def _process_headings(text: str) -> str:
    """Add emojis to Markdown headings and plain ALL-CAPS section titles."""
    lines = []
    for line in text.splitlines():
        # Markdown headings
        if re.match(r"^#{1,4}\s+\S", line):
            line = _add_section_emoji(line)
        # Plain bold headings (**text:**)
        elif re.match(r"^\*\*[^*]+[:\*]{1,2}\s*$", line):
            inner = line.strip("*: ")
            line = _add_section_emoji(f"**{inner}:**")
        lines.append(line)
    return "\n".join(lines)


def format_answer(raw_answer: str, language: str = "en") -> str:
    """
    Format a raw LLM response into a polished chatbot answer.

    Args:
        raw_answer: The unprocessed string returned by the LLM.
        language:   ISO 639-1 language code (e.g. 'en', 'hi').

    Returns:
        Cleaned, emoji-enhanced, consistently formatted answer string.
    """
    if not ENABLE_FORMATTING:
        return raw_answer

    if not raw_answer or not raw_answer.strip():
        return raw_answer

    text = raw_answer

    # 1. Normalise bullets
    text = _normalise_bullets(text)

    # 2. Add emojis to section headings (only for English — avoid garbling other scripts)
    if language == "en":
        text = _process_headings(text)

    # 3. Clean up spacing
    text = _clean_spacing(text)

    # 4. Truncate if too long
    text = _truncate_if_needed(text)

    return text
