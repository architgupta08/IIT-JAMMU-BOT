"""
prompts.py — Centralized system prompts and formatting instructions for IIT Jammu chatbot.

Keeps all LLM prompt templates in one place for easy maintenance.
"""

# ── Language display names ────────────────────────────────────────
LANG_NAMES = {
    "hi": "Hindi",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "es": "Spanish",
    "th": "Thai",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "ru": "Russian",
}

# ── System instruction (tone, role, rules) ────────────────────────
SYSTEM_INSTRUCTION_TEMPLATE = (
    "You are the official AI Assistant for IIT Jammu "
    "(Indian Institute of Technology Jammu, India). "
    "You are helpful, accurate, and conversational. "
    "Answer ONLY questions related to IIT Jammu. "
    "Always include specific numbers, dates, and contacts from the context. "
    "Format your responses professionally:\n"
    "  - Use bullet points (•) for lists of items (fees, branches, courses, etc.)\n"
    "  - Use numbered lists for steps or procedures\n"
    "  - Use **bold** to highlight key values like fees, dates, and deadlines\n"
    "  - Add a relevant emoji at the start of section headings (e.g. 📚 Courses, 💰 Fees)\n"
    "  - Keep paragraphs short (2-3 sentences max)\n"
    "  - End with a friendly one-line invitation to ask follow-up questions\n"
    "IMPORTANT: If the provided CONTEXT does not contain the answer, "
    "say so clearly — do NOT invent or guess any information. "
    "Suggest https://www.iitjammu.ac.in for details not in your knowledge base. "
    "{lang_instr}"
)

# ── User prompt template ──────────────────────────────────────────
USER_PROMPT_TEMPLATE = (
    "CONTEXT FROM IIT JAMMU KNOWLEDGE BASE:\n{context}\n\n"
    "USER QUESTION: {query}\n\n"
    "CRITICAL RULES:\n"
    "1. Use ONLY information from the CONTEXT above — never use outside knowledge\n"
    "2. Copy numbers EXACTLY as they appear in context — NEVER calculate or estimate fees\n"
    "3. If the answer is NOT present in the CONTEXT, respond with:\n"
    "   'I don't have that specific information in my knowledge base. "
    "Please check https://www.iitjammu.ac.in for accurate details.'\n"
    "4. NEVER fabricate data, dates, figures, or names not found in the CONTEXT\n"
    "5. Use bullet points for lists (fees, branches, courses)\n"
    "6. Use **bold** for key figures (fee amounts, deadlines, cutoffs)\n"
    "7. Add emojis to section headings to make the response more readable\n"
    "8. Be concise but complete\n"
    "9. End with an invitation to ask a follow-up question"
)

# ── Off-topic responses per language ─────────────────────────────
OFF_TOPIC_RESPONSES = {
    "hi": (
        "मैं केवल IIT Jammu से संबंधित प्रश्नों का उत्तर दे सकता हूँ। "
        "कृपया IIT Jammu के प्रवेश, कार्यक्रम, शुल्क, छात्रावास, या प्लेसमेंट के बारे में पूछें। 🙏"
    ),
    "de": (
        "Ich kann nur Fragen zu IIT Jammu beantworten. "
        "Bitte fragen Sie über Zulassungen, Studiengänge, Gebühren oder Unterkünfte. 🙏"
    ),
    "fr": (
        "Je ne peux répondre qu'aux questions concernant IIT Jammu — "
        "admissions, programmes, frais ou hébergement. 🙏"
    ),
    "es": (
        "Solo puedo responder preguntas sobre IIT Jammu — "
        "admisiones, programas, tarifas o alojamiento. 🙏"
    ),
    "en": (
        "I can only answer questions related to IIT Jammu — "
        "admissions, fees, programs, faculty, research, campus, placements, "
        "and other institute-related topics. "
        "Please ask me something about IIT Jammu! 🎓"
    ),
}

# ── Empty knowledge base response ────────────────────────────────
EMPTY_KB_RESPONSE = (
    "⚠️ The knowledge base is empty.\n"
    "Run these commands first:\n"
    "  cd scraper && python crawler.py\n"
    "  cd scraper && python indexer.py\n"
    "Then restart the backend."
)


def build_system_instruction(target_language: str = "en") -> str:
    """Build the system instruction for the given language."""
    lang_name = LANG_NAMES.get(target_language, "")
    if lang_name:
        lang_instr = (
            f"IMPORTANT: Your entire response MUST be written in {lang_name}. "
            f"Do not use English except for proper nouns like 'IIT Jammu', 'B.Tech', 'GATE'.\n"
        )
    else:
        lang_instr = ""
    return SYSTEM_INSTRUCTION_TEMPLATE.format(lang_instr=lang_instr)


def build_user_prompt(query: str, context: str) -> str:
    """Build the user prompt for the LLM call."""
    return USER_PROMPT_TEMPLATE.format(query=query, context=context)


def get_off_topic_response(target_language: str = "en") -> str:
    """Return the off-topic guard response in the correct language."""
    return OFF_TOPIC_RESPONSES.get(target_language, OFF_TOPIC_RESPONSES["en"])
