"""
scheduler.py — Standalone APScheduler for IIT Jammu Knowledge Base Auto-Update
================================================================================
Runs the web crawler (crawler_v3.py) and knowledge index builder (indexer.py)
on startup and then every SCRAPER_INTERVAL_HOURS (default: 2 hours).

USAGE (standalone):
  python scheduler.py          # start scheduler (blocks until Ctrl-C)

ENV VARS:
  SCRAPER_ENABLED         true|false  (default: true)
  SCRAPER_INTERVAL_HOURS  float       (default: 2.0)
  SCRAPER_MAX_PAGES       int         (default: 500)
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# ── Config from environment ───────────────────────────────────────────────────
SCRAPER_ENABLED: bool = os.getenv("SCRAPER_ENABLED", "true").lower() == "true"
SCRAPER_INTERVAL_HOURS: float = float(os.getenv("SCRAPER_INTERVAL_HOURS", "2"))
SCRAPER_MAX_PAGES: int = int(os.getenv("SCRAPER_MAX_PAGES", "500"))

SCRAPER_DIR: Path = Path(__file__).resolve().parent

# Max lines of subprocess output to forward to the logger per run
_MAX_LOG_LINES: int = 30

# ── Scrape history (in-memory) ────────────────────────────────────────────────
scrape_history: dict = {
    "last_run": None,
    "last_status": None,
    "run_count": 0,
}


async def run_crawl_and_index() -> None:
    """
    Run crawler_v3.py then indexer.py as subprocesses.
    Errors are logged but never re-raised so the scheduler keeps running.
    Updates scrape_history after each attempt.
    """
    scrape_history["run_count"] += 1
    run_num = scrape_history["run_count"]
    scrape_history["last_run"] = datetime.now(timezone.utc).isoformat()

    logger.info("🕷️  [Run #%d] Starting crawl (max_pages=%d) …", run_num, SCRAPER_MAX_PAGES)

    # ── Step 1: Web crawler ───────────────────────────────────────────────────
    crawler_ok = False
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "crawler_v3.py", "--max", str(SCRAPER_MAX_PAGES),
            cwd=str(SCRAPER_DIR),
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

    # ── Step 2: Rebuild index ─────────────────────────────────────────────────
    logger.info("🌲 [Run #%d] Rebuilding knowledge index …", run_num)
    indexer_ok = False
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "indexer.py",
            cwd=str(SCRAPER_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            for line in stdout.decode(errors="replace").splitlines()[-_MAX_LOG_LINES:]:
                logger.info("  [indexer] %s", line)
        if proc.returncode == 0:
            logger.info("✅ [Run #%d] Index rebuilt successfully", run_num)
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
        run_num,
        scrape_history["last_status"],
        SCRAPER_INTERVAL_HOURS,
    )


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure an AsyncIOScheduler.
    Call scheduler.start() to begin and scheduler.shutdown() to stop it.
    """
    scheduler = AsyncIOScheduler()

    if SCRAPER_ENABLED:
        scheduler.add_job(
            run_crawl_and_index,
            trigger=IntervalTrigger(hours=SCRAPER_INTERVAL_HOURS),
            id="kb_update",
            name="Knowledge Base Auto-Update",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(
            "⏰ Scheduler configured: crawl every %.1f h (max_pages=%d)",
            SCRAPER_INTERVAL_HOURS,
            SCRAPER_MAX_PAGES,
        )
    else:
        logger.info("ℹ️  Scraper disabled via SCRAPER_ENABLED=false")

    return scheduler


# ── Standalone entry-point ────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    async def _main() -> None:
        scheduler = create_scheduler()
        scheduler.start()
        logger.info("🚀 Standalone scheduler running — press Ctrl-C to stop")

        # Run first crawl immediately, then APScheduler handles subsequent runs
        if SCRAPER_ENABLED:
            logger.info("🕷️  Starting initial crawl on startup …")
            await run_crawl_and_index()

        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            scheduler.shutdown(wait=False)
            logger.info("🛑 Scheduler stopped")

    asyncio.run(_main())
