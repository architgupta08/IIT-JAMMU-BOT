"""
main.py — FastAPI Backend for IIT Jammu AI Assistant (Fixed)
"""
import asyncio
import os
import logging
import sys
import time
import uuid
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from models import (
    ChatRequest, ChatResponse, HealthResponse,
    IndexStatsResponse, SuggestedQuestionsResponse, SourceNode
)
from rag_engine import get_rag_engine, get_knowledge_tree, reload_knowledge_base
from language_handler import LanguageContext

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ── Fix INDEX_FILE path — resolve ../data/... from project root ───
def _resolve_index_path():
    raw = os.getenv("INDEX_FILE", "data/processed/iitj_index.json")
    if raw.startswith("../"):
        resolved = raw[3:]  # strip leading ../
        os.environ["INDEX_FILE"] = resolved
        return resolved
    return raw

INDEX_FILE_RESOLVED = _resolve_index_path()

# ── Rate limiter ──────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


UPDATE_INTERVAL_SECONDS: int = int(os.getenv("KB_UPDATE_INTERVAL_SECONDS", "3600"))  # default: 1 hour


async def _auto_update_knowledge_base() -> None:
    """
    Background task: run the web crawler then rebuild the knowledge index.
    Runs once on startup. Failures are logged but never crash the backend.
    """
    scraper_dir = Path(__file__).resolve().parent.parent / "scraper"

    # ── Step 1: Web crawler ───────────────────────────────────────
    logger.info("🕷️  Auto-update: starting web crawler (max_pages=500) …")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "crawler_v3.py", "--max", "500",
            cwd=str(scraper_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            for line in stdout.decode(errors="replace").splitlines()[-30:]:
                logger.info("  [crawler] %s", line)
        if proc.returncode == 0:
            logger.info("✅ Auto-update: crawler finished successfully")
        else:
            logger.warning("⚠  Auto-update: crawler exited with code %d", proc.returncode)
    except Exception as exc:
        logger.warning("⚠  Auto-update: crawler failed — %s", exc)

    # ── Step 2: Rebuild index ─────────────────────────────────────
    logger.info("🌲 Auto-update: rebuilding knowledge index …")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "indexer.py",
            cwd=str(scraper_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            for line in stdout.decode(errors="replace").splitlines()[-30:]:
                logger.info("  [indexer] %s", line)
        if proc.returncode == 0:
            logger.info("✅ Auto-update: index rebuilt — reloading knowledge tree …")
            reload_knowledge_base()
            get_knowledge_tree()
            get_rag_engine()
            logger.info("✅ Auto-update complete — knowledge base is up to date")
        else:
            logger.warning("⚠  Auto-update: indexer exited with code %d", proc.returncode)
    except Exception as exc:
        logger.warning("⚠  Auto-update: indexer failed — %s", exc)


async def _scheduled_kb_updater() -> None:
    """
    Infinite background loop that refreshes the knowledge base every
    KB_UPDATE_INTERVAL_SECONDS (default 3600 = 1 hour).

    The first run happens immediately at startup; subsequent runs are
    spaced by UPDATE_INTERVAL_SECONDS regardless of how long each run takes.
    """
    while True:
        run_start = asyncio.get_event_loop().time()
        logger.info(
            "🔄 Scheduled KB update starting (interval=%ds) …",
            UPDATE_INTERVAL_SECONDS,
        )
        await _auto_update_knowledge_base()

        elapsed = asyncio.get_event_loop().time() - run_start
        sleep_for = max(0.0, UPDATE_INTERVAL_SECONDS - elapsed)
        logger.info(
            "⏰ Next KB update in %.0f s (≈ %.1f min)",
            sleep_for,
            sleep_for / 60,
        )
        await asyncio.sleep(sleep_for)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting IIT Jammu AI Assistant …")

    # Kick off the hourly scheduler in the background so the backend starts immediately.
    # It runs the crawler+indexer on startup, then repeats every UPDATE_INTERVAL_SECONDS.
    _update_task = asyncio.create_task(_scheduled_kb_updater())

    try:
        tree = get_knowledge_tree()
        logger.info(f"✅ Knowledge tree: {tree.count_nodes()} nodes")
        if tree.count_nodes() == 0:
            logger.warning("⚠  Knowledge tree is EMPTY — run scraper/indexer.py first")
    except Exception as e:
        logger.error(f"⚠  Startup warning: {e}")

    try:
        get_rag_engine()
        logger.info("✅ RAG engine ready")
    except Exception as e:
        logger.error(f"⚠  RAG engine init error: {e}")
    yield
    logger.info("🛑 Shutting down — cancelling KB updater …")
    _update_task.cancel()
    try:
        await _update_task
    except asyncio.CancelledError:
        logger.info("✅ KB updater cancelled cleanly")


app = FastAPI(
    title="IIT Jammu AI Assistant",
    description="VectorlessRAG chatbot powered by Google Gemini",
    version="1.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # widen for dev; restrict in production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({time.time()-start:.2f}s)")
    return response


# ── Routes ────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    try:
        tree = get_knowledge_tree()
        return HealthResponse(
            status="ok",
            index_loaded=tree.count_nodes() > 0,
            total_nodes=tree.count_nodes(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        )
    except Exception as e:
        return HealthResponse(
            status=f"degraded: {e}", index_loaded=False,
            total_nodes=0, gemini_model=os.getenv("GEMINI_MODEL", "unknown")
        )


@app.get("/index/stats", response_model=IndexStatsResponse, tags=["Knowledge Base"])
async def index_stats():
    tree = get_knowledge_tree()
    return IndexStatsResponse(
        total_sections=len(tree.get_root_nodes()),
        total_nodes=tree.count_nodes(),
        top_level_sections=tree.get_top_level_titles(),
        last_updated=tree.get_last_updated()
    )


@app.get("/suggestions", response_model=SuggestedQuestionsResponse, tags=["Chat"])
async def suggestions():
    return SuggestedQuestionsResponse(questions=[
        "What are the B.Tech programs offered at IIT Jammu?",
        "What is the fee structure for B.Tech 2024-25?",
        "How do I apply for M.Tech admission?",
        "What is the GATE cutoff for CSE at IIT Jammu?",
        "Tell me about hostel facilities and charges",
        "Who are the faculty members in Computer Science?",
        "What are the placement statistics for 2024?",
        "What scholarships are available for students?",
        "What is the eligibility for PhD programs?",
        "How to reach the IIT Jammu campus?",
    ])


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
@limiter.limit(f"{os.getenv('RATE_LIMIT_PER_MINUTE', '30')}/minute")
async def chat(request: Request, body: ChatRequest):
    session_id = body.session_id or str(uuid.uuid4())
    lang_ctx = LanguageContext(body.message, forced_lang=body.language)
    logger.info(f"[{session_id}] '{body.message[:60]}' | lang={lang_ctx.detected_lang}")

    try:
        engine = get_rag_engine()
        result = await engine.answer(body.message, target_language=lang_ctx.detected_lang)
    except Exception as e:
        logger.error(f"[{session_id}] RAG engine exception:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"AI engine error: {type(e).__name__}: {e}")

    return ChatResponse(
        answer=result.answer,
        detected_language=lang_ctx.detected_lang,
        sources=[SourceNode(title=s.title, path=s.path, node_id=s.node_id) for s in result.sources],
        confidence=round(result.confidence, 2),
        session_id=session_id
    )


@app.post("/debug/chat", tags=["Debug"])
async def debug_chat(request: Request, body: ChatRequest):
    """
    Debug endpoint — returns full error tracebacks instead of generic messages.
    Use this when /chat returns 'I encountered an error…' to see the real cause.
    Remove or protect this endpoint before going to production.
    """
    session_id = "debug_" + str(uuid.uuid4())[:8]
    lang_ctx = LanguageContext(body.message)
    debug_info = {
        "message": body.message,
        "detected_language": lang_ctx.detected_lang,
        "session_id": session_id,
        "index_file": INDEX_FILE_RESOLVED,
        "gemini_model": os.getenv("GEMINI_MODEL"),
        "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        "tree_nodes": 0,
        "error": None,
        "traceback": None,
        "answer": None,
    }

    try:
        tree = get_knowledge_tree()
        debug_info["tree_nodes"] = tree.count_nodes()

        engine = get_rag_engine()
        result = await engine.answer(body.message, target_language=lang_ctx.detected_lang)
        debug_info["answer"] = result.answer
        debug_info["confidence"] = result.confidence
        debug_info["sources"] = [{"title": s.title, "path": s.path} for s in result.sources]

    except Exception as e:
        debug_info["error"] = f"{type(e).__name__}: {e}"
        debug_info["traceback"] = traceback.format_exc()
        logger.error(f"Debug chat error:\n{traceback.format_exc()}")

    return JSONResponse(content=debug_info)


@app.get("/debug/gemini", tags=["Debug"])
async def debug_gemini():
    """Test Gemini API connection directly and return real error if any."""
    info = {
        "gemini_model": os.getenv("GEMINI_MODEL"),
        "key_prefix": os.getenv("GEMINI_API_KEY", "")[:8] + "…",
        "sdk": None,
        "status": None,
        "error": None,
        "response": None,
    }
    try:
        from google import genai as g
        info["sdk"] = "google-genai (new SDK) ✓"
    except ImportError:
        try:
            import google.generativeai as g
            info["sdk"] = "google-generativeai (old SDK) — gemini-2.5-flash NOT supported"
        except ImportError:
            info["sdk"] = "NO Gemini SDK found"
            info["error"] = "Run: pip install google-genai>=1.0.0"
            return JSONResponse(content=info, status_code=500)

    try:
        from gemini_client import get_gemini_client
        client = get_gemini_client()
        response = await client.generate("Reply with exactly one word: WORKING")
        info["status"] = "ok"
        info["response"] = response
    except Exception as e:
        info["status"] = "error"
        info["error"] = f"{type(e).__name__}: {e}"
        info["traceback"] = traceback.format_exc()

    return JSONResponse(content=info, status_code=200 if info["status"] == "ok" else 500)


# ── Error handlers ────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse(status_code=404, content={"error": "Not found", "path": str(request.url.path)})

@app.exception_handler(500)
async def server_error(request: Request, exc):
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=True
    )
