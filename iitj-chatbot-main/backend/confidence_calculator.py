"""
confidence_calculator.py — Real confidence score calculation for IIT Jammu chatbot.

Replaces the hardcoded confidence = 0.85 with a multi-factor score based on:
  1. Keyword overlap between query and top retrieved nodes
  2. Number of source nodes returned
  3. Answer completeness (length and structure)
  4. Data freshness (how recent the index is)
"""
import re
import logging
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────
# Weight of each factor in the final score (must sum to 1.0)
_W_KEYWORD   = 0.40   # keyword overlap between query and top nodes
_W_SOURCES   = 0.25   # number of high-scoring sources
_W_COMPLETENESS = 0.25  # answer length & structural signals
_W_FRESHNESS = 0.10   # index freshness

# Thresholds
_FRESHNESS_DAYS_FRESH   = 30   # index younger than this → max freshness score
_FRESHNESS_DAYS_STALE   = 365  # index older than this → min freshness score
_MIN_ANSWER_LENGTH      = 40   # characters; below this → low completeness
_GOOD_ANSWER_LENGTH     = 200  # characters; above this → high completeness

# Stop words excluded from keyword overlap calculation
_STOP_WORDS = {
    "what", "is", "the", "at", "in", "for", "of", "a", "an", "and", "or",
    "tell", "me", "about", "how", "do", "i", "can", "you", "please",
    "give", "list", "show", "are", "there", "any", "which", "does",
    "कौन", "से", "में", "प्रोग्राम", "है", "हैं", "क्या",
}


def _tokenize(text: str) -> set:
    """Tokenize text into lowercase words, removing stop words."""
    return {
        w.lower()
        for w in re.findall(r"[\w₹]+", text)
        if w.lower() not in _STOP_WORDS and len(w) > 1
    }


def _keyword_overlap_score(query: str, nodes) -> float:
    """
    Score [0, 1] based on how well the top nodes cover the query keywords.

    Measures: what fraction of the query's non-trivial keywords appear in
    at least one of the top nodes (title, summary, or text).
    """
    q_words = _tokenize(query)
    if not q_words:
        return 0.5  # neutral when query has no meaningful tokens

    matched = 0
    for word in q_words:
        for node in nodes:
            combined = (node.title + " " + node.summary + " " + node.text).lower()
            if word in combined:
                matched += 1
                break  # count each query word once

    return matched / len(q_words)


def _source_count_score(nodes, node_scores: Optional[List[float]] = None) -> float:
    """
    Score [0, 1] based on number and quality of retrieved sources.

    - 0 nodes  → 0.0
    - 1 node   → 0.4
    - 2 nodes  → 0.6
    - 3+ nodes → 0.8 base, boosted by average node score if provided
    """
    n = len(nodes)
    if n == 0:
        return 0.0
    if n == 1:
        base = 0.4
    elif n == 2:
        base = 0.6
    else:
        base = 0.8

    # If raw keyword scores were supplied, give a small boost for high-quality hits
    if node_scores:
        avg_score = sum(node_scores) / len(node_scores)
        # Normalise: assume max reasonable score is 50 (title + summary + text hits)
        quality_boost = min(0.2, avg_score / 50 * 0.2)
        base = min(1.0, base + quality_boost)

    return base


def _answer_completeness_score(answer: str) -> float:
    """
    Score [0, 1] based on answer length and presence of formatting signals.
    """
    length = len(answer.strip())
    if length < _MIN_ANSWER_LENGTH:
        return 0.2

    # Length component
    if length >= _GOOD_ANSWER_LENGTH:
        length_score = 1.0
    else:
        length_score = (length - _MIN_ANSWER_LENGTH) / (_GOOD_ANSWER_LENGTH - _MIN_ANSWER_LENGTH)

    # Structural bonus: bullet points, numbers, dates, bold text, emojis
    structural_signals = [
        bool(re.search(r"[•\-\*]\s", answer)),          # bullet points
        bool(re.search(r"\d+", answer)),                  # numbers/dates
        bool(re.search(r"\*\*[^*]+\*\*", answer)),        # bold text
        bool(re.search(r"\d{4}", answer)),                 # years
        bool(re.search(r"₹|\bRs\.?\b|\bINR\b", answer)), # currency
        bool(re.search(r"[😊🎓💰📚🏛️✅⚠️🔍]", answer)),   # emojis
    ]
    structural_score = sum(structural_signals) / len(structural_signals)

    # Penalty for "I don't have" answers — bot admitted it doesn't know
    if re.search(r"i don.t have|not in (the|my) knowledge|check.*iitjammu", answer, re.I):
        return max(0.1, length_score * 0.3)

    return (length_score * 0.7) + (structural_score * 0.3)


def _freshness_score(last_updated: Optional[str]) -> float:
    """
    Score [0, 1] based on how recently the knowledge base was updated.

    Returns 0.7 (neutral) when last_updated is unavailable.
    """
    if not last_updated:
        return 0.7  # neutral — we can't tell

    try:
        # Parse ISO-8601 date/datetime string
        if "T" in last_updated:
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(last_updated).replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_days = (now - dt).days

        if age_days <= _FRESHNESS_DAYS_FRESH:
            return 1.0
        if age_days >= _FRESHNESS_DAYS_STALE:
            return 0.3
        # Linear interpolation between fresh and stale
        ratio = (age_days - _FRESHNESS_DAYS_FRESH) / (
            _FRESHNESS_DAYS_STALE - _FRESHNESS_DAYS_FRESH
        )
        return round(1.0 - (ratio * 0.7), 3)
    except Exception:
        logger.debug("Could not parse last_updated: %s", last_updated)
        return 0.7


def calculate_confidence(
    query: str,
    nodes,
    answer: str,
    last_updated: Optional[str] = None,
    node_scores: Optional[List[float]] = None,
) -> float:
    """
    Calculate a real confidence score [0.0, 1.0] for a chatbot answer.

    Args:
        query:        The user's original question.
        nodes:        List of FlatNode objects retrieved by the RAG engine.
        answer:       The answer text produced by the LLM.
        last_updated: ISO-8601 string from the knowledge-base index metadata.
        node_scores:  Optional raw keyword scores for each node.

    Returns:
        A float in [0.0, 1.0] rounded to 2 decimal places.
    """
    if not nodes:
        return 0.25  # no sources → low confidence regardless of answer

    f_keyword     = _keyword_overlap_score(query, nodes)
    f_sources     = _source_count_score(nodes, node_scores)
    f_completeness = _answer_completeness_score(answer)
    f_freshness   = _freshness_score(last_updated)

    score = (
        _W_KEYWORD      * f_keyword
        + _W_SOURCES    * f_sources
        + _W_COMPLETENESS * f_completeness
        + _W_FRESHNESS  * f_freshness
    )

    # Cap to [0.05, 0.97] — never claim perfect confidence or complete ignorance
    score = max(0.05, min(0.97, score))

    logger.debug(
        "confidence: keyword=%.2f sources=%.2f completeness=%.2f freshness=%.2f → %.2f",
        f_keyword, f_sources, f_completeness, f_freshness, score,
    )
    return round(score, 2)
