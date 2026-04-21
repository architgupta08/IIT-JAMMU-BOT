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
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

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

# ── Scheduler config from environment ────────────────────────────
SCRAPER_ENABLED: bool = os.getenv("SCRAPER_ENABLED", "true").lower() == "true"
SCRAPER_INTERVAL_HOURS: float = float(os.getenv("SCRAPER_INTERVAL_HOURS", "2"))
SCRAPER_MAX_PAGES: int = int(os.getenv("SCRAPER_MAX_PAGES", "500"))

_SCRAPER_DIR: Path = Path(__file__).resolve().parent.parent / "scraper"

# Max lines of subprocess output to forward to the logger per run
_MAX_LOG_LINES: int = 30

# ── Scrape history (in-memory) ────────────────────────────────────
scrape_history: dict = {
    "last_run": None,
    "last_status": None,
    "run_count": 0,
}


async def _auto_update_knowledge_base() -> None:
    """
    Run the web crawler then rebuild the knowledge index, then hot-reload
    the in-memory knowledge base.  Failures are logged but never crash the backend.
    """
    scrape_history["run_count"] += 1
    run_num = scrape_history["run_count"]
    scrape_history["last_run"] = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Web crawler ───────────────────────────────────────
    logger.info(
        "🕷️  [Run #%d] Starting web crawler (max_pages=%d) …",
        run_num, SCRAPER_MAX_PAGES,
    )
    crawler_ok = False
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "crawler_v3.py", "--max", str(SCRAPER_MAX_PAGES),
            cwd=str(_SCRAPER_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            for line in stdout.decode(errors="replace").splitlines()[-_MAX_LOG_LINES:]:
                logger.info("  [crawler] %s", line)
        if proc.returncode == 0:
            logger.info("✅ [Run #%d] Crawler finished successfully", run_num)
            crawler_ok = True
        else:
            logger.warning(
                "⚠  [Run #%d] Crawler exited with code %d", run_num, proc.returncode
            )
    except Exception as exc:
        logger.warning("⚠  [Run #%d] Crawler failed — %s", run_num, exc)

    # ── Step 2: Rebuild index ─────────────────────────────────────
    logger.info("🌲 [Run #%d] Rebuilding knowledge index …", run_num)
    indexer_ok = False
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "indexer.py",
            cwd=str(_SCRAPER_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            for line in stdout.decode(errors="replace").splitlines()[-_MAX_LOG_LINES:]:
                logger.info("  [indexer] %s", line)
        if proc.returncode == 0:
            logger.info(
                "✅ [Run #%d] Index rebuilt — reloading knowledge tree …", run_num
            )
            reload_knowledge_base()
            get_knowledge_tree()
            get_rag_engine()
            logger.info(
                "✅ [Run #%d] Knowledge base is up to date", run_num
            )
            indexer_ok = True
        else:
            logger.warning(
                "⚠  [Run #%d] Indexer exited with code %d", run_num, proc.returncode
            )
    except Exception as exc:
        logger.warning("⚠  [Run #%d] Indexer failed — %s", run_num, exc)

    if indexer_ok:
        scrape_history["last_status"] = "success"
    elif crawler_ok:
        scrape_history["last_status"] = "partial"
    else:
        scrape_history["last_status"] = "failed"

    logger.info(
        "📋 [Run #%d] Status: %s | Next run in %.1f h",
        run_num, scrape_history["last_status"], SCRAPER_INTERVAL_HOURS,
    )


def _create_scheduler() -> AsyncIOScheduler:
    """Create and configure an AsyncIOScheduler for background KB updates."""
    scheduler = AsyncIOScheduler()
    if SCRAPER_ENABLED:
        scheduler.add_job(
            _auto_update_knowledge_base,
            trigger=IntervalTrigger(hours=SCRAPER_INTERVAL_HOURS),
            id="kb_update",
            name="Knowledge Base Auto-Update",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(
            "⏰ Scheduler configured: crawl every %.1f h (max_pages=%d)",
            SCRAPER_INTERVAL_HOURS, SCRAPER_MAX_PAGES,
        )
    else:
        logger.info("ℹ️  Scraper disabled via SCRAPER_ENABLED=false")
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting IIT Jammu AI Assistant …")

    # Start APScheduler for periodic background KB updates
    scheduler = _create_scheduler()
    scheduler.start()
    logger.info("✅ Background scheduler started")

    # Load existing knowledge base immediately (before first crawl finishes)
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

    # Run first crawl immediately in the background (non-blocking)
    if SCRAPER_ENABLED:
        logger.info("🕷️  Starting initial crawl …")
        asyncio.create_task(_auto_update_knowledge_base())

    yield

    logger.info("🛑 Shutting down — stopping scheduler …")
    scheduler.shutdown(wait=False)
    logger.info("✅ Scheduler stopped")


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
