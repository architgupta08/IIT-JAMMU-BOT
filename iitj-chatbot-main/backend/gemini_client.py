"""
groq_client.py - Groq API Client (Free & Unlimited)
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from groq import Groq
from prompts import build_system_instruction, build_user_prompt

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
        system = build_system_instruction(target_language)
        prompt = build_user_prompt(query, context)
        return await self.generate(prompt, system_instruction=system)

_client: Optional[GeminiClient] = None

def get_gemini_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
