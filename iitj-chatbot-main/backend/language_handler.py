"""
language_handler.py — Multilingual support for IIT Jammu Chatbot

Detects user language → processes query in English → responds in user's language
Uses langdetect (free, offline) for detection.
Translation is handled by Gemini itself (no paid translation API needed).
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Language code to name mapping
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ur": "Urdu",
    "ks": "Kashmiri",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "ar": "Arabic",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "pt": "Portuguese",
}

# Languages that use Devanagari-related scripts — detect more carefully
INDIAN_LANGUAGES = {"hi", "mr", "ne", "ks", "bho"}


# Common romanized Hindi/Urdu words that langdetect misidentifies
_HINDI_ROMANIZED = {
    "hai", "hain", "kya", "kaise", "kitna", "kitni", "kitne",
    "mein", "ka", "ki", "ke", "aur", "nahi", "nahin", "kab",
    "kahan", "kyun", "kaun", "btao", "batao", "bataiye",
    "wala", "wali", "iska", "uska", "yahan", "wahan",
    "hota", "hoti", "hote", "chahiye", "liya", "liye",
    "kon", "koun", "accha", "theek", "bilkul", "bahut",
}

def _is_romanized_hindi(text: str) -> bool:
    """Detect romanized Hindi/Urdu (e.g. 'fees kitni hai')."""
    import re
    words = re.findall(r"\b\w+\b", text.lower())
    matches = sum(1 for w in words if w in _HINDI_ROMANIZED)
    return matches >= 2


def detect_language(text: str) -> str:
    """
    Detect the language of input text.
    Returns ISO 639-1 language code (e.g., 'en', 'hi').
    Falls back to 'en' on failure.
    """
    # Check for romanized Hindi FIRST (before langdetect misidentifies it)
    if _is_romanized_hindi(text):
        logger.debug(f"Detected romanized Hindi for: {text[:50]}")
        return "hi"

    try:
        from langdetect import detect, LangDetectException
        if len(text.strip()) < 15:
            return "en"
        lang = detect(text)
        # Sanity check: langdetect sometimes returns 'de'/'af' for romanized Hindi
        # If it returns a rare language for short mixed text, trust romanized check instead
        if lang not in {"en", "hi", "de", "fr", "es", "it", "pt", "th", "ar", "zh-cn", "ja", "ko"}:
            return "en"
        logger.debug(f"Detected language: {lang} for text: {text[:50]}")
        return lang
    except ImportError:
        logger.warning("langdetect not installed, defaulting to English")
        return "en"
    except Exception as e:
        logger.warning(f"Language detection failed: {e}, defaulting to English")
        return "en"


def get_language_name(code: str) -> str:
    """Get human-readable name for a language code."""
    return LANGUAGE_NAMES.get(code, code.upper())


def normalize_language_code(code: str) -> str:
    """
    Normalize language codes to ensure compatibility.
    e.g., 'zh-cn' → 'zh', strips region subtags for most languages.
    """
    if code in ("zh-cn", "zh-tw"):
        return code  # Keep Chinese variants
    return code.split("-")[0]


def should_translate(lang_code: str) -> bool:
    """Returns True if the response needs to be in a non-English language."""
    normalized = normalize_language_code(lang_code)
    return normalized != "en"


def build_language_instruction(lang_code: str) -> str:
    """
    Build the language instruction string for Gemini prompts.
    If language is English, returns empty string (no special instruction needed).
    """
    lang_code = normalize_language_code(lang_code)
    if lang_code == "en":
        return ""
    lang_name = get_language_name(lang_code)
    return (
        f"CRITICAL INSTRUCTION: You MUST respond entirely in {lang_name} ({lang_code}). "
        f"Do not use any English words unless they are proper nouns (like 'IIT Jammu', 'B.Tech', 'GATE'). "
        f"The user wrote in {lang_name}, so respond in {lang_name}. "
    )


def extract_english_query(text: str, source_lang: str) -> str:
    """
    For non-English queries, we use the original text for retrieval
    but may need an English translation for tree navigation.
    This is a simple heuristic — Gemini handles translation in the prompt itself.
    """
    # For tree navigation, we pass the original text; Gemini is multilingual enough
    # to understand the intent even in non-English input.
    return text


class LanguageContext:
    """
    Holds language metadata for a single request.
    """
    def __init__(self, raw_query: str, forced_lang: Optional[str] = None):
        self.raw_query = raw_query
        self.detected_lang = (
            normalize_language_code(forced_lang)
            if forced_lang
            else detect_language(raw_query)
        )
        self.is_non_english = should_translate(self.detected_lang)
        self.lang_name = get_language_name(self.detected_lang)
        self.gemini_instruction = build_language_instruction(self.detected_lang)

    def __repr__(self):
        return f"LanguageContext(lang={self.detected_lang}, non_english={self.is_non_english})"
