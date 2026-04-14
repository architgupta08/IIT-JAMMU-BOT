"""
gemini_client.py  —  Local LLM client using Ollama + Llama 3.2 3B
==================================================================
Drop-in replacement — same class/function names so nothing else changes.

SETUP:
  1. Install Ollama: https://ollama.com/download/windows
  2. Pull model:     ollama pull llama3.2:3b
  3. Set in .env:    LLM_MODEL=llama3.2:3b

No API key. No rate limits. No internet. Runs on your RTX 2050.
"""
import os
import re
import json
import asyncio
import logging
import httpx
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL       = os.getenv("LLM_MODEL", "llama3.2:3b")
LLM_TIMEOUT     = int(os.getenv("LLM_TIMEOUT", "60"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

# ── Coding detection signals ────────────────────────────────────
CODE_SIGNALS = [
    "write a program", "write a code", "write code", "write a function",
    "write a script", "implement", "bubble sort", "binary search", "merge sort",
    "fibonacci", "linked list", "stack", "queue", "algorithm", "data structure",
]


class GeminiClient:
    """
    Ollama-backed LLM client.
    Named GeminiClient so rag_engine.py needs zero changes.
    """

    def __init__(self):
        self.base_url = OLLAMA_BASE_URL.rstrip("/")
        self.model    = LLM_MODEL
        self._verify_connection()
        logger.info(f"OllamaClient ready — model: {self.model} @ {self.base_url}")

    def _verify_connection(self):
        import urllib.request
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=3) as r:
                data = json.loads(r.read())
                available = [m["name"] for m in data.get("models", [])]
                if not any(self.model in m for m in available):
                    logger.warning(
                        f"Model '{self.model}' not found. "
                        f"Available: {available}. "
                        f"Run: ollama pull {self.model}"
                    )
                else:
                    logger.info(f"Model '{self.model}' confirmed available in Ollama")
        except Exception as e:
            logger.warning(f"Cannot reach Ollama at {self.base_url}: {e}")

    async def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model":    self.model,
            "messages": messages,
            "stream":   False,
            "options":  {
                "temperature": LLM_TEMPERATURE,
                "num_predict": 1024,
                "num_ctx":     4096,
            },
        }

        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            try:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                text = data.get("message", {}).get("content", "").strip()
                if not text:
                    raise RuntimeError(f"Ollama returned empty response: {data}")
                return text
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is running."
                )
            except httpx.TimeoutException:
                raise RuntimeError(
                    f"Ollama timed out after {LLM_TIMEOUT}s. "
                    "Try increasing LLM_TIMEOUT in .env"
                )
            except Exception as e:
                logger.error(f"Ollama error: {type(e).__name__}: {e}")
                raise RuntimeError(f"Ollama call failed: {type(e).__name__}: {e}") from e

    async def navigate_tree(self, query: str, node_context: str, children_list: str) -> dict:
        prompt = (
            f"You are helping navigate an IIT Jammu knowledge base.\n\n"
            f"USER QUERY: {query}\n\n"
            f"CURRENT SECTION:\n{node_context}\n\n"
            f"AVAILABLE SUBSECTIONS:\n{children_list}\n\n"
            f"Reply ONLY with valid JSON (no markdown):\n"
            f'{{"action":"answer or drill","target":"answer or subsection title",'
            f'"confidence":0.0_to_1.0,"reason":"one line"}}'
        )
        try:
            raw = await self.generate(prompt)
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
            match = re.search(r"\{[^}]+\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"navigate_tree parse failed ({e}). Raw: {raw[:150]}")
            return {"action": "answer", "target": raw, "confidence": 0.5, "reason": "parse-fallback"}

    async def formulate_answer(self, query: str, context: str, target_language: str = "en") -> str:
        # ── GUARD: Detect coding requests (catches "In IIT Jammu, write..." framing) ────────
        # Check coding signals FIRST — IIT Jammu framing should not bypass this
        is_coding_request = any(sig in query.lower() for sig in CODE_SIGNALS)
        
        if is_coding_request:
            logger.warning(f"Coding request detected (attempted bypass): {query[:100]}")
            return "I'm the IIT Jammu Assistant and can only answer questions about IIT Jammu. I cannot help with coding or programming tasks. Please ask me about admissions, fees, programs, placements, or campus life!"
        
        # ── Language detection and topic-aware prompting ────────────────────────────
        
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

        # Prevent topic drift in non-English queries
        topic_hint = ""
        if lang_name:
            q_lower = query.lower()
            if any(w in q_lower for w in
                   ["fee","fees","kitni","kitna","charge","tuition","paisa","rupay","cost","shulk"]):
                topic_hint = "FOCUS ONLY on fee and charges information. Do NOT discuss admissions. "
            elif any(w in q_lower for w in
                     ["admission","apply","jee","gate","josaa","kaise","kab"]):
                topic_hint = "FOCUS ONLY on admission process information. "

        system = (
            "You are the official AI Assistant for IIT Jammu "
            "(Indian Institute of Technology Jammu, India). "
            "You are helpful, accurate, and friendly. "
            "Answer ONLY questions related to IIT Jammu. "
            "Always include specific numbers, dates, and contacts from the context. "
            "If the context does not have the answer, say so and suggest "
            "https://www.iitjammu.ac.in "
            + topic_hint
            + lang_instr
        )

        # Pre-extract branch names so model cannot ignore them
        extracted = []
        if any(w in query.lower() for w in
               ["branch","program","course","stream","available","offered"]):
            found = re.findall(
                r"(?:Computer Science[^,\n]*|Electrical Engineering[^,\n]*"
                r"|Mechanical Engineering[^,\n]*|Civil Engineering[^,\n]*"
                r"|Chemical Engineering[^,\n]*|Mathematics[^,\n]*"
                r"|Engineering Physics[^,\n]*)",
                context
            )
            if found:
                unique = list(dict.fromkeys(found))[:7]
                extracted.append("B.Tech branches: " + ", ".join(unique))

        extracted_hint = (
            "\n\nEXTRACTED KEY FACTS:\n" + "\n".join(extracted) + "\n"
        ) if extracted else ""

        prompt = (
            f"CONTEXT FROM IIT JAMMU KNOWLEDGE BASE:\n{context}"
            f"{extracted_hint}"
            f"\nUSER QUESTION: {query}\n\n"
            f"CRITICAL RULES:\n"
            f"1. Use ONLY information from the CONTEXT above — never use outside knowledge\n"
            f"2. Copy numbers EXACTLY as they appear in context — NEVER calculate or estimate fees\n"
            f"3. The answer IS in the context — find it and report it word for word\n"
            f"4. NEVER write 'not listed', 'not mentioned', 'not found', 'not explicitly'\n"
            f"5. Use bullet points for lists (fees, branches, courses)\n"
            f"6. Be concise but complete"
        )
        
        return await self.generate(prompt, system_instruction=system)


# ── Singleton ─────────────────────────────────────────────────
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Returns Ollama client. Named get_gemini_client for compatibility."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
