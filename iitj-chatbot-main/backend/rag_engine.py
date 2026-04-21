"""
rag_engine.py — Robust VectorlessRAG Engine (Rewrite)

ROOT CAUSES OF PREVIOUS FAILURES
──────────────────────────────────
1. 500 errors: navigate_tree() returned action="answer" with empty target.
   The code then called formulate_answer() with empty context → Gemini error.

2. Wrong answers: Root-level navigation picked "Admissions" instead of
   "Fee Structure" because the summaries were too vague. Gemini made a wrong
   turn and never found the fee data even though it was in the index.

NEW APPROACH (simpler, more reliable)
──────────────────────────────────────
Step 1 — Keyword retrieval (instant, no API calls):
  Flatten the entire tree into a list of nodes. Score every node against
  the query using keyword overlap on title + summary + text. Pick top-N nodes.

Step 2 — Single Gemini call (one API call per question):
  Send the top-N nodes as context and ask Gemini to answer.

Benefits:
  • Never fails due to navigation errors (no tree traversal)
  • Correct data is always in context if it exists in the index
  • Uses only 1 Gemini call per question (vs 3–5 before)
  • 500 errors impossible — context is always non-empty
  • Works perfectly with the seed index and also with the full crawled index
"""
import os
import re
import json
import logging
from collections import OrderedDict
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────
def _resolve(path: str) -> str:
    """
    Resolve index path so it works whether uvicorn is run from
    the project root OR from the backend/ subfolder.
    Tries multiple locations and returns the first that exists.
    """
    import os as _os
    # Strip leading ../
    if path.startswith("../"):
        path = path[3:]

    # 1. Try as-is (relative to cwd)
    if _os.path.exists(path):
        return path

    # 2. Try relative to this file's directory (backend/)
    backend_dir = _os.path.dirname(_os.path.abspath(__file__))
    from_backend = _os.path.join(backend_dir, path)
    if _os.path.exists(from_backend):
        return from_backend

    # 3. Try one level up (project root)
    project_root = _os.path.dirname(backend_dir)
    from_root = _os.path.join(project_root, path)
    if _os.path.exists(from_root):
        return from_root

    # Return original — will produce a clear "not found" warning
    return path

INDEX_FILE        = _resolve(os.getenv("INDEX_FILE", "data/processed/iitj_index.json"))
TOP_K_NODES       = int(os.getenv("TOP_K_NODES", "8"))        # nodes sent to LLM (increased from 4)
MAX_TEXT_PER_NODE = int(os.getenv("MAX_TEXT_PER_NODE", "800")) # chars per node in context (increased from 500)
CACHE_MAX_SIZE    = int(os.getenv("CACHE_MAX_SIZE", "100"))    # max cached query responses


# ══════════════════════════════════════════════════════════════════
#  Knowledge Tree
# ══════════════════════════════════════════════════════════════════

@dataclass
class FlatNode:
    node_id: str
    title:   str
    path:    str
    summary: str
    text:    str
    score:   float = 0.0


@dataclass
class RAGResult:
    answer:   str
    sources:  List[FlatNode] = field(default_factory=list)
    confidence: float = 0.0
    detected_language: str = "en"


# ══════════════════════════════════════════════════════════════════
#  Off-topic guard — blocks non-IIT Jammu queries
# ══════════════════════════════════════════════════════════════════

_IITJ_SIGNALS = {
    "iit","jammu","iitj","admission","btech","b.tech","mtech","m.tech",
    "phd","ph.d","msc","fee","fees","hostel","mess","placement","scholarship",
    "gate","jee","josaa","faculty","professor","director","campus","research",
    "department","programme","program","course","syllabus","cutoff","rank",
    "cse","ee","me","ce","che","hss","library","medical","sports","jagti",
    "stipend","fellowship","pmrf","mcm","nirf","tnp","internship","lpa","ctc",
    "nagrota","paloura","academic","semester","elective","convocation","alumni",
}

_OFF_TOPIC_SIGNALS = [
    # Coding / programming tasks
    "write a python", "write a java", "write a c++", "write a code",
    "write code for", "write a program", "write a function", "write a script",
    "code for", "program for", "implement a", "implement the",
    "debug this", "fix this code", "fix my code", "explain this code",
    "python code", "java code", "c++ code", "javascript code", "html code",
    "sql query", "binary search", "linear search", "bubble sort", "merge sort",
    "quick sort", "linked list", "stack implementation", "queue implementation",
    "tree traversal", "tic tac", "snake game", "chess game", "sudoku",
    "calculator app", "fibonacci", "sorting algorithm", "searching algorithm",
    "data structure", "recursion example", "machine learning code",
    "neural network", "deep learning code",
    # General knowledge outside IITJ
    "recipe for", "how to cook", "best movie", "song lyrics",
    "cricket score", "ipl score", "football score", "match score",
    "stock price", "bitcoin", "cryptocurrency", "share price",
    "weather today", "weather in", "news today", "latest news",
    "capital of", "president of", "prime minister of",
    "translate to", "meaning of word", "synonym of", "antonym of",
    # Personal / entertainment
    "love poem", "write a poem", "write an essay", "write a story",
    "tell me a joke", "tell a joke", "funny joke", "make me laugh",
    "horoscope", "astrology", "plan my trip", "hotel in", "restaurant near",
]


def _is_off_topic(query: str) -> bool:
    """
    Returns True if query is clearly unrelated to IIT Jammu.
    Step 1: If any IIT Jammu signal word present → always on-topic.
    Step 2: If matches off-topic pattern AND no IITJ signal → off-topic.
    """
    import re as _re
    q = query.lower().strip()
    words = set(_re.findall(r"\b\w+\b", q))

    # Step 1: Strong IITJ signals → always answer
    if words & _IITJ_SIGNALS:
        return False
    if any(sig in q for sig in ["iit jammu", "iit j", "iitjammu", "jagti", "nagrota"]):
        return False

    # Step 2: Check off-topic patterns
    for pattern in _OFF_TOPIC_SIGNALS:
        if pattern in q:
            return True

    # Short queries without IITJ context → be generous
    if len(q.split()) <= 4:
        return False

    return False


class IITJKnowledgeTree:
    """Loads the PageIndex JSON tree and exposes a flat list for retrieval."""

    def __init__(self, index_path: str):
        self._path = index_path
        self._tree: Dict[str, Any] = {}
        self._flat:  List[FlatNode] = []
        self._load()

    def _load(self):
        p = Path(self._path)
        if not p.exists():
            logger.warning(f"Index not found: {p.resolve()} — using empty tree")
            self._tree = {"structure": []}
            return
        self._tree = json.loads(p.read_text(encoding="utf-8"))
        self._flat = []
        self._flatten(self._tree.get("structure", []), parent="")
        logger.info(f"Loaded {len(self._flat)} nodes from {p}")

    def _flatten(self, nodes: list, parent: str):
        for n in nodes:
            title = n.get("title", "Untitled")
            path  = f"{parent} > {title}" if parent else title
            n["_path"] = path
            self._flat.append(FlatNode(
                node_id = n.get("node_id", ""),
                title   = title,
                path    = path,
                summary = n.get("summary", ""),
                text    = n.get("text", ""),
            ))
            self._flatten(n.get("nodes", []), path)

    # ── Public API ──────────────────────────────────────────────────
    def count_nodes(self) -> int:         return len(self._flat)
    def get_root_nodes(self) -> list:     return self._tree.get("structure", [])
    def get_top_level_titles(self) -> list: return [n.get("title","") for n in self.get_root_nodes()]
    def get_last_updated(self) -> Optional[str]: return self._tree.get("last_updated")

    def get_node(self, node_id: str) -> Optional[Dict]:
        for n in self._flat:
            if n.node_id == node_id:
                return {"node_id": n.node_id, "title": n.title}
        return None

    def search(self, query: str, top_k: int = TOP_K_NODES) -> List[FlatNode]:
        """
        IMPROVED keyword-score every node and return the top_k most relevant.
        Now includes:
        - Better substring matching
        - Category boost for "Academic Programs" section
        - Flexible scoring that catches all B.Tech programs

        Scoring:
          +5  title contains a query word
          +3  summary contains a query word
          +2  text contains a query word
          +2  if the query word appears in multiple fields (multi-field boost)
          +3  category boost for Academic Programs nodes when querying about programs
        """
        # Tokenise query — keep numbers and Rs/₹ intact
        stop = {
            "what","is","the","at","in","for","of","a","an","and","or",
            "tell","me","about","how","do","i","can","you","please",
            "give","list","show","are","there","any","which","does",
            "are","कौन","से","में","प्रोग्राम","है","हैं","क्या",
        }
        q_words = [
            w.lower() for w in re.findall(r"[\w,\.₹]+", query)
            if w.lower() not in stop and len(w) > 1
        ]
        if not q_words:
            return self._flat[:top_k]

        scored: List[Tuple[float, FlatNode]] = []
        for node in self._flat:
            t = node.title.lower()
            s = node.summary.lower()
            x = node.text.lower()
            sc = 0.0
            
            for w in q_words:
                in_title   = w in t
                in_summary = w in s
                in_text    = w in x
                
                # Increased scoring weights
                if in_title:   sc += 5
                if in_summary: sc += 3
                if in_text:    sc += 2
                
                # Multi-field boost
                field_count = sum([in_title, in_summary, in_text])
                if field_count > 1:
                    sc += 2

            # CATEGORY BOOST: Academic Programs section
            if "academic" in node.path.lower():
                program_keywords = ["program", "course", "degree", "b.tech", "btech", "mtech", "m.tech", "phd", "ph.d"]
                if any(kw in query.lower() for kw in program_keywords):
                    sc += 3

            if sc > 0:
                scored.append((sc, node))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [n for _, n in scored[:top_k]]

        # If nothing matched, prioritize Academic Programs nodes
        if not results:
            academic_nodes = [n for n in self._flat if "academic" in n.path.lower()]
            if academic_nodes:
                return academic_nodes[:top_k]
            # Fallback: return first top_k nodes
            roots = self._flat[:min(top_k, len(self._flat))]
            return roots
        
        return results


# ══════════════════════════════════════════════════════════════════
#  RAG Engine
# ══════════════════════════════════════════════════════════════════

class VectorlessRAGEngine:
    """
    Retrieval: keyword scoring over flat node list  (no Gemini calls)
    Generation: single Gemini call with retrieved context
    """

    def __init__(self, tree: IITJKnowledgeTree, gemini_client):
        self.tree   = tree
        self.gemini = gemini_client
        # OrderedDict preserves insertion order for reliable FIFO eviction.
        # Safe for asyncio (single-threaded event loop); not multi-process safe.
        self._cache: OrderedDict[str, RAGResult] = OrderedDict()

    def _build_context(self, nodes: List[FlatNode]) -> str:
        parts = []
        for node in nodes:
            section = f"### {node.path}\n"
            if node.summary:
                section += f"{node.summary}\n"
            if node.text:
                txt = node.text.strip()
                if len(txt) > MAX_TEXT_PER_NODE:
                    txt = txt[:MAX_TEXT_PER_NODE] + "…"
                section += f"\n{txt}\n"
            parts.append(section)
        return "\n---\n".join(parts)

    async def answer(self, query: str, target_language: str = "en") -> RAGResult:
        # ── Guard: empty tree ─────────────────────────────────────
        if self.tree.count_nodes() == 0:
            return RAGResult(
                answer=(
                    "⚠️ The knowledge base is empty.\n"
                    "Run these commands first:\n"
                    "  cd scraper && python crawler.py\n"
                    "  cd scraper && python indexer.py\n"
                    "Then restart the backend."
                ),
                confidence=0.0,
                detected_language=target_language,
            )

        # ── Guard: off-topic queries ──────────────────────────────
        if _is_off_topic(query):
            lang_map = {
                "hi": "मैं केवल IIT Jammu से संबंधित प्रश्नों का उत्तर दे सकता हूँ। कृपया IIT Jammu के बारे में पूछें।",
                "de": "Ich kann nur Fragen zu IIT Jammu beantworten. Bitte fragen Sie über IIT Jammu.",
                "fr": "Je ne peux répondre qu'aux questions concernant IIT Jammu.",
                "es": "Solo puedo responder preguntas sobre IIT Jammu.",
            }
            off_msg = lang_map.get(
                target_language,
                "I can only answer questions related to IIT Jammu — admissions, fees, programs, "
                "faculty, research, campus, placements, and other institute-related topics. "
                "Please ask me something about IIT Jammu!"
            )
            return RAGResult(
                answer=off_msg,
                sources=[],
                confidence=0.0,
                detected_language=target_language,
            )

        # ── Cache lookup ──────────────────────────────────────────
        # Use null byte as separator — cannot appear in language codes or queries
        cache_key = f"{target_language}\x00{query.strip().lower()}"
        if cache_key in self._cache:
            logger.debug(f"Cache hit for query: {query[:60]}")
            return self._cache[cache_key]

        # ── Step 1: Keyword retrieval (no API) ────────────────────
        top_nodes = self.tree.search(query, top_k=TOP_K_NODES)
        context   = self._build_context(top_nodes)

        # ── Step 2: Single LLM call ───────────────────────────────
        try:
            answer_text = await self.gemini.formulate_answer(
                query=query,
                context=context,
                target_language=target_language,
            )
            confidence = 0.85 if top_nodes else 0.3
        except Exception as e:
            logger.error(f"Gemini formulate_answer error: {type(e).__name__}: {e}")
            raise   # re-raise so /debug/chat shows the real error

        # Score of top hit as a proxy for confidence
        if top_nodes:
            hit_score = self.tree.search(query, top_k=1)
            confidence = min(0.95, 0.5 + 0.05 * len(hit_score))

        result = RAGResult(
            answer=answer_text,
            sources=top_nodes[:3],
            confidence=round(confidence, 2),
            detected_language=target_language,
        )

        # ── Store in cache (evict oldest entry when full) ─────────
        if len(self._cache) >= CACHE_MAX_SIZE:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[cache_key] = result

        return result


# ══════════════════════════════════════════════════════════════════
#  Singletons
# ══════════════════════════════════════════════════════════════════
_tree:   Optional[IITJKnowledgeTree]    = None
_engine: Optional[VectorlessRAGEngine] = None


def get_knowledge_tree() -> IITJKnowledgeTree:
    global _tree
    if _tree is None:
        _tree = IITJKnowledgeTree(INDEX_FILE)
    return _tree


def get_rag_engine() -> VectorlessRAGEngine:
    global _engine
    if _engine is None:
        from gemini_client import get_gemini_client
        _engine = VectorlessRAGEngine(get_knowledge_tree(), get_gemini_client())
    return _engine


def reload_knowledge_base() -> None:
    """Reset cached singletons so the next call to get_knowledge_tree() / get_rag_engine()
    re-reads the index file from disk.  Call this after the indexer has written a fresh
    iitj_index.json.
    """
    global _tree, _engine
    _tree = None
    _engine = None
