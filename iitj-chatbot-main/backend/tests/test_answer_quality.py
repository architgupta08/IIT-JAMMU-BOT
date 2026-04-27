"""
test_answer_quality.py — Unit tests for answer formatting, confidence calculation,
and response enhancement components of the IIT Jammu chatbot.

Run from the repo root:
    python -m pytest iitj-chatbot-main/backend/tests/test_answer_quality.py -v

Or from backend/:
    python -m pytest tests/test_answer_quality.py -v
"""
import sys
import os

# Allow imports from backend/ whether tests run from root or backend/
_backend_dir = os.path.join(os.path.dirname(__file__), "..")
if _backend_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_backend_dir))

import pytest
from dataclasses import dataclass, field
from typing import List, Optional


# ── Minimal FlatNode stub (avoids importing the full RAG engine) ──
@dataclass
class _FlatNode:
    node_id: str
    title: str
    path: str
    summary: str
    text: str
    score: float = 0.0


# ══════════════════════════════════════════════════════════════════
#  answer_formatter tests
# ══════════════════════════════════════════════════════════════════

class TestAnswerFormatter:
    """Tests for answer_formatter.format_answer()"""

    def setup_method(self):
        from answer_formatter import format_answer
        self.format_answer = format_answer

    def test_returns_string(self):
        result = self.format_answer("Hello world", language="en")
        assert isinstance(result, str)

    def test_empty_input_returns_empty(self):
        assert self.format_answer("") == ""
        assert self.format_answer("   ") == "   "

    def test_normalises_dash_bullets(self):
        raw = "- Item one\n- Item two\n- Item three"
        result = self.format_answer(raw, language="en")
        assert "• Item one" in result
        assert "• Item two" in result
        # Original dash bullets should be gone
        assert "- Item one" not in result

    def test_normalises_star_bullets(self):
        raw = "* Option A\n* Option B"
        result = self.format_answer(raw, language="en")
        assert "• Option A" in result

    def test_removes_excessive_blank_lines(self):
        raw = "Line one\n\n\n\n\nLine two"
        result = self.format_answer(raw, language="en")
        # Should have at most 2 consecutive newlines
        assert "\n\n\n" not in result

    def test_adds_emoji_to_fee_heading(self):
        raw = "## Fee Structure\nThe fee is ₹2,00,000 per year."
        result = self.format_answer(raw, language="en")
        assert "💰" in result

    def test_adds_emoji_to_admission_heading(self):
        raw = "## Admission Process\nApply via JoSAA."
        result = self.format_answer(raw, language="en")
        assert "📝" in result

    def test_no_emoji_injection_for_non_english(self):
        raw = "## शुल्क संरचना\n₹2,00,000 प्रति वर्ष।"
        result = self.format_answer(raw, language="hi")
        # For non-English, heading emoji injection is skipped
        # (the raw text itself may already contain emojis via LLM output — we don't add more)
        assert isinstance(result, str)

    def test_truncation_adds_note(self):
        long_text = "A" * 3000
        # Temporarily set a low limit
        import answer_formatter as af
        original = af.MAX_RESPONSE_LENGTH
        af.MAX_RESPONSE_LENGTH = 200
        result = af._truncate_if_needed(long_text)
        af.MAX_RESPONSE_LENGTH = original
        assert "truncated" in result.lower() or "iitjammu.ac.in" in result

    def test_preserves_existing_emojis(self):
        raw = "💰 **Fee Structure**\nThe annual fee is ₹2,00,000."
        result = self.format_answer(raw, language="en")
        # Should not add a duplicate emoji next to existing one
        assert result.count("💰") == 1


# ══════════════════════════════════════════════════════════════════
#  confidence_calculator tests
# ══════════════════════════════════════════════════════════════════

class TestConfidenceCalculator:
    """Tests for confidence_calculator.calculate_confidence()"""

    def setup_method(self):
        from confidence_calculator import calculate_confidence
        self.calculate_confidence = calculate_confidence

    def _make_node(self, title="", summary="", text=""):
        return _FlatNode(node_id="test_node", title=title, path=title,
                         summary=summary, text=text)

    def test_returns_float_in_range(self):
        nodes = [self._make_node("B.Tech Fee Structure", "Annual tuition fee", "Fee is ₹2,00,000")]
        score = self.calculate_confidence("What is the B.Tech fee?", nodes, "The fee is ₹2,00,000.")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_no_nodes_returns_low_confidence(self):
        score = self.calculate_confidence("What is the fee?", [], "I don't know.")
        assert score <= 0.30

    def test_high_keyword_overlap_raises_score(self):
        nodes = [
            self._make_node(
                "B.Tech Fee Structure",
                "B.Tech tuition fee information",
                "The annual fee for B.Tech is ₹2,00,000 per year.",
            )
        ]
        low_nodes = [self._make_node("Random Page", "Unrelated content", "Something else")]
        score_high = self.calculate_confidence("What is the B.Tech fee?", nodes, "Fee is ₹2,00,000.")
        score_low  = self.calculate_confidence("What is the B.Tech fee?", low_nodes, "I don't know.")
        assert score_high > score_low

    def test_more_sources_raises_score(self):
        one_node   = [self._make_node("Fee", "fee info", "fee ₹2L")]
        three_nodes = [
            self._make_node("Fee", "fee info", "fee ₹2L"),
            self._make_node("Hostel Fee", "hostel fee info", "hostel fee ₹50k"),
            self._make_node("Scholarship", "scholarship details", "MCM scholarship"),
        ]
        score_one   = self.calculate_confidence("fee", one_node,   "fee ₹2L")
        score_three = self.calculate_confidence("fee", three_nodes, "fee ₹2L, hostel ₹50k")
        assert score_three >= score_one

    def test_long_structured_answer_raises_completeness(self):
        nodes = [self._make_node("Fee", "fee info", "₹2,00,000")]
        short_answer = "Fee is ₹2L."
        long_answer  = (
            "## 💰 B.Tech Fee Structure\n\n"
            "The annual tuition fee for B.Tech at IIT Jammu is **₹2,00,000**.\n\n"
            "• Semester fee: ₹1,00,000\n"
            "• Hostel: ₹50,000\n"
            "• Mess: ₹30,000\n\n"
            "Fees are payable before **31 July 2025**. "
            "Feel free to ask more questions!"
        )
        score_short = self.calculate_confidence("fee", nodes, short_answer)
        score_long  = self.calculate_confidence("fee", nodes, long_answer)
        assert score_long > score_short

    def test_i_dont_know_answer_lowers_completeness(self):
        nodes = [self._make_node("Fee", "fee info", "₹2L")]
        answer_unknown = "I don't have that specific information in my knowledge base."
        answer_known   = "The B.Tech fee at IIT Jammu is **₹2,00,000** per year."
        score_unknown = self.calculate_confidence("fee", nodes, answer_unknown)
        score_known   = self.calculate_confidence("fee", nodes, answer_known)
        assert score_known > score_unknown

    def test_freshness_score_fresh_index(self):
        from confidence_calculator import _freshness_score
        from datetime import datetime, timezone
        recent = datetime.now(timezone.utc).isoformat()
        assert _freshness_score(recent) == 1.0

    def test_freshness_score_old_index(self):
        from confidence_calculator import _freshness_score
        assert _freshness_score("2020-01-01") <= 0.35

    def test_freshness_score_none(self):
        from confidence_calculator import _freshness_score
        score = _freshness_score(None)
        assert 0.5 <= score <= 0.9  # neutral range

    def test_score_is_capped(self):
        """Score must never be 0.0 or 1.0 (capped at 0.05..0.97)."""
        nodes = [self._make_node("test", "test", "test")] * 10
        score = self.calculate_confidence("test", nodes, "test " * 100)
        assert score <= 0.97
        score_empty = self.calculate_confidence("xyz123", [], "")
        assert score_empty >= 0.05


# ══════════════════════════════════════════════════════════════════
#  response_enhancer tests
# ══════════════════════════════════════════════════════════════════

class TestResponseEnhancer:
    """Tests for response_enhancer functions."""

    def setup_method(self):
        from response_enhancer import get_related_suggestions, build_footer
        self.get_related_suggestions = get_related_suggestions
        self.build_footer = build_footer

    # ── Suggestions ───────────────────────────────────────────────

    def test_returns_list(self):
        result = self.get_related_suggestions("What is the fee?", "The fee is ₹2,00,000.")
        assert isinstance(result, list)

    def test_fee_query_returns_fee_suggestions(self):
        suggestions = self.get_related_suggestions(
            "What is the B.Tech fee?",
            "The annual fee is ₹2,00,000."
        )
        # Should return up to 3 suggestions
        assert len(suggestions) <= 3
        # At least one should mention fee or scholarship
        combined = " ".join(suggestions).lower()
        assert any(kw in combined for kw in ["fee", "scholarship", "hostel"])

    def test_placement_query_returns_placement_suggestions(self):
        suggestions = self.get_related_suggestions(
            "What are the placement statistics?",
            "The average placement package is 12 LPA."
        )
        combined = " ".join(suggestions).lower()
        assert any(kw in combined for kw in ["placement", "recruit", "package", "internship"])

    def test_empty_query_returns_list(self):
        result = self.get_related_suggestions("", "")
        assert isinstance(result, list)

    def test_max_suggestions_limit(self):
        import response_enhancer as re_mod
        original = re_mod.MAX_SUGGESTIONS
        re_mod.MAX_SUGGESTIONS = 2
        suggestions = self.get_related_suggestions(
            "What is the B.Tech fee?", "₹2,00,000 per year."
        )
        re_mod.MAX_SUGGESTIONS = original
        assert len(suggestions) <= 2

    def test_suggestions_disabled(self):
        import response_enhancer as re_mod
        original = re_mod.ENABLE_SUGGESTIONS
        re_mod.ENABLE_SUGGESTIONS = False
        result = self.get_related_suggestions("fee", "₹2L")
        re_mod.ENABLE_SUGGESTIONS = original
        assert result == []

    # ── Footer ────────────────────────────────────────────────────

    def test_footer_returns_string(self):
        @dataclass
        class _Source:
            title: str
            path: str
            node_id: str = "n1"

        sources = [_Source("Fee Structure", "Programs > B.Tech > Fees")]
        footer = self.build_footer(sources, confidence=0.85, response_time_ms=320.5)
        assert isinstance(footer, str)

    def test_footer_contains_confidence_badge_high(self):
        @dataclass
        class _Source:
            title: str = "Test"
            path: str = "Test"
            node_id: str = "n1"

        footer = self.build_footer([_Source()], confidence=0.85)
        assert "High confidence" in footer or "🟢" in footer

    def test_footer_contains_confidence_badge_medium(self):
        @dataclass
        class _Source:
            title: str = "Test"
            path: str = "Test"
            node_id: str = "n1"

        footer = self.build_footer([_Source()], confidence=0.60)
        assert "Medium confidence" in footer or "🟡" in footer

    def test_footer_contains_confidence_badge_low(self):
        @dataclass
        class _Source:
            title: str = "Test"
            path: str = "Test"
            node_id: str = "n1"

        footer = self.build_footer([_Source()], confidence=0.30)
        assert "Low confidence" in footer or "🔴" in footer

    def test_footer_disabled(self):
        import response_enhancer as re_mod
        original = re_mod.ENABLE_FOOTER
        re_mod.ENABLE_FOOTER = False

        @dataclass
        class _Source:
            title: str = "Test"
            path: str = "Test"
            node_id: str = "n1"

        footer = self.build_footer([_Source()], confidence=0.85)
        re_mod.ENABLE_FOOTER = original
        assert footer == ""

    def test_footer_contains_timestamp(self):
        @dataclass
        class _Source:
            title: str = "Test"
            path: str = "Test"
            node_id: str = "n1"

        footer = self.build_footer([_Source()], confidence=0.80)
        # Should contain year (UTC timestamp)
        import re
        assert re.search(r"\d{4}", footer)

    def test_footer_with_no_sources(self):
        footer = self.build_footer([], confidence=0.50)
        # Should still return a footer string
        assert isinstance(footer, str)


# ══════════════════════════════════════════════════════════════════
#  prompts tests
# ══════════════════════════════════════════════════════════════════

class TestPrompts:
    """Tests for prompts.py helper functions."""

    def test_build_system_instruction_english(self):
        from prompts import build_system_instruction
        instr = build_system_instruction("en")
        assert "IIT Jammu" in instr
        assert "bullet" in instr.lower()

    def test_build_system_instruction_hindi_contains_hindi_instr(self):
        from prompts import build_system_instruction
        instr = build_system_instruction("hi")
        assert "Hindi" in instr

    def test_build_user_prompt_contains_query_and_context(self):
        from prompts import build_user_prompt
        prompt = build_user_prompt("What is the fee?", "Fee: ₹2,00,000")
        assert "What is the fee?" in prompt
        assert "Fee: ₹2,00,000" in prompt

    def test_get_off_topic_response_english(self):
        from prompts import get_off_topic_response
        resp = get_off_topic_response("en")
        assert "IIT Jammu" in resp

    def test_get_off_topic_response_hindi(self):
        from prompts import get_off_topic_response
        resp = get_off_topic_response("hi")
        assert "IIT Jammu" in resp

    def test_get_off_topic_response_unknown_lang_falls_back_to_english(self):
        from prompts import get_off_topic_response
        resp = get_off_topic_response("xx")
        assert "IIT Jammu" in resp
