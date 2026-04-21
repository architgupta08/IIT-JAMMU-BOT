"""
groq_client.py - Groq API Client (Free & Unlimited)
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set in .env")

client = Groq(api_key=GROQ_API_KEY)

class GeminiClient:
    def __init__(self):
        self.model = GROQ_MODEL
        logger.info(f"✅ Groq model ready - {GROQ_MODEL}")

    async def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        try:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1024,
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq error: {e}")
            raise RuntimeError(f"Groq call failed: {e}")

    async def formulate_answer(self, query: str, context: str, target_language: str = "en") -> str:
        lang_map = {
            "hi": "Hindi",
            "de": "German",
            "fr": "French",
            "it": "Italian",
            "pt": "Portuguese",
            "es": "Spanish",
            "th": "Thai",
        }
        lang_name = lang_map.get(target_language, "")
        lang_instr = (
            f"IMPORTANT: Your entire response MUST be written in {lang_name}. "
            f"Do not use English except for proper nouns like 'IIT Jammu', 'B.Tech', 'GATE'.\n"
            if lang_name else ""
        )

        system = (
            "You are the official AI Assistant for IIT Jammu "
            "(Indian Institute of Technology Jammu, India). "
            "You are helpful, accurate, and trustworthy. "
            "Answer ONLY questions related to IIT Jammu. "
            "Always include specific numbers, dates, and contacts from the context. "
            "IMPORTANT: If the provided CONTEXT does not contain the answer, "
            "you MUST say so clearly — do NOT invent or guess any information. "
            "Suggest https://www.iitjammu.ac.in for details not in your knowledge base. "
            + lang_instr
        )

        prompt = (
            f"CONTEXT FROM IIT JAMMU KNOWLEDGE BASE:\n{context}\n\n"
            f"USER QUESTION: {query}\n\n"
            f"CRITICAL RULES:\n"
            f"1. Use ONLY information from the CONTEXT above — never use outside knowledge\n"
            f"2. Copy numbers EXACTLY as they appear in context — NEVER calculate or estimate fees\n"
            f"3. If the answer is NOT present in the CONTEXT, respond with:\n"
            f"   'I don't have that specific information in my knowledge base. "
            f"Please check https://www.iitjammu.ac.in for accurate details.'\n"
            f"4. NEVER fabricate data, dates, figures, or names not found in the CONTEXT\n"
            f"5. Use bullet points for lists (fees, branches, courses)\n"
            f"6. Be concise but complete"
        )
        
        return await self.generate(prompt, system_instruction=system)

_client: Optional[GeminiClient] = None

def get_gemini_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
