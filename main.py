"""
main.py — Pipeline Orchestrator
"""

import logging
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from pipeline import step1_scraper, step2_detector, step3_reporter
from pipeline import db
from pipeline.storage import upload_json

# ── Logging: console only (Supabase handler added after run starts) ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("orchestrator")

# Silence noisy HTTP loggers so they never reach the Supabase handler
for _noisy in ("httpx", "httpcore", "hpack", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_current_run_id: str | None = None


class SupabaseLogHandler(logging.Handler):
    """
    Streams pipeline log lines to pipeline_logs table.
    Recursion-safe: httpx/httpcore logs are silenced above so they
    never reach this handler. The _emitting guard is a second safety net.
    """
    _emitting: bool = False

    def emit(self, record: logging.LogRecord):
        # Double-guard: skip if already inside an emit or no run active
        if self._emitting or not _current_run_id:
            return
        # Skip any HTTP / DB library logs that slip through
        if record.name in ("httpx", "httpcore", "hpack", "urllib3",
                           "pipeline.db", "supabase"):
            return
        self._emitting = True
        try:
            level = record.levelname.lower()
            if level not in ("debug", "info", "warning", "error"):
                level = "info"
            step = None
            for s in (1, 2, 3):
                if f"step{s}" in record.name:
                    step = s
                    break
            db.log_to_db(_current_run_id, self.format(record),
                         level=level, step=step)
        except Exception:
            pass  # never raise inside a log handler
        finally:
            self._emitting = False


# Attach Supabase handler to root logger
_sb_handler = SupabaseLogHandler()
_sb_handler.setFormatter(logging.Formatter("%(name)s — %(message)s"))
logging.getLogger().addHandler(_sb_handler)


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _safe_filename(s: str, max_len: int = 80) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", s)[:max_len].strip("_")


# ══════════════════════════════════════════════════════════════
#  CORE ORCHESTRATION
# ══════════════════════════════════════════════════════════════

def orchestrate(triggered_by: str = "manual") -> str | None:
    global _current_run_id

    # ── Guard: only one run at a time ────────────────────────
    active = db.get_active_run()
    if active:
        log.info("Run %s already active — enqueueing", active["id"])
        db.enqueue_pending(triggered_by)
        return None

    # ── Load config from Supabase pipeline_config ─────────────
    config = db.load_pipeline_config()
    run_id = str(uuid.uuid4())
    _current_run_id = run_id

    config_snapshot = {
        "sites":        config.get("sites", []),
        "date_ranges":  [list(dr) for dr in config.get("date_ranges", [])],
        "search_terms": config.get("search_terms", []),
        "country":      config.get("country", "in"),
        "triggered_by": triggered_by,
    }

    # ── Create DB run record ──────────────────────────────────
    db.create_run(run_id, config_snapshot)
    db.update_run(run_id, status="running", current_step=0)

    log.info("═" * 65)
    log.info("Pipeline Run started: %s  (triggered_by=%s)", run_id, triggered_by)
    log.info("Sites      : %s", config.get("sites", []))
    log.info("Date ranges: %s", config.get("date_ranges", []))
    log.info("═" * 65)

    # ══════════════════════════════════════════════════════════
    #  STEP 1 — Scrape
    # ══════════════════════════════════════════════════════════
    log.info("▶ STEP 1: Scraping articles…")
    db.update_run(run_id, current_step=1)

    try:
        articles = step1_scraper.run(config)
    except Exception as exc:
        log.error("Step 1 FAILED: %s", exc, exc_info=True)
        db.fail_run(run_id, step=1, error=str(exc))
        _start_next_pending()
        return None

    log.info("✓ Step 1 complete — %d articles scraped", len(articles))
    db.update_run(run_id, step1_articles=len(articles))

    article_id_map: dict[int, str | None] = {}
    for idx, article in enumerate(articles):
        slug    = _safe_filename(article.get("title", f"article_{idx}"))
        s3_path = f"runs/{run_id}/step1_scraped/{slug}__{idx:04d}.json"
        s3_url  = upload_json(s3_path, article)
        art_id  = db.insert_article(run_id, article, storage_path=s3_url)
        article_id_map[idx] = art_id

    # ══════════════════════════════════════════════════════════
    #  STEP 2 — Detect
    # ══════════════════════════════════════════════════════════
    log.info("▶ STEP 2: Detecting phobia (taxonomy-enriched)…")
    db.update_run(run_id, current_step=2)

    try:
        detections = step2_detector.run(articles, config)
    except Exception as exc:
        log.error("Step 2 FAILED: %s", exc, exc_info=True)
        db.fail_run(run_id, step=2, error=str(exc))
        _start_next_pending()
        return None

    total_detections = sum(d["summary"]["total_detections"] for d in detections)
    log.info("✓ Step 2 complete — %d total detections", total_detections)
    db.update_run(run_id, step2_detections=total_detections)

    detection_id_map: dict[int, str | None] = {}
    for idx, det in enumerate(detections):
        slug    = _safe_filename(det.get("title", f"article_{idx}"))
        s3_path = f"runs/{run_id}/step2_detections/{slug}__{idx:04d}__detection.json"
        s3_url  = upload_json(s3_path, det)
        det_id  = db.insert_detection(
            run_id,
            article_id=article_id_map.get(idx),
            detection=det,
            storage_path=s3_url,
        )
        detection_id_map[idx] = det_id

    # ══════════════════════════════════════════════════════════
    #  STEP 3 — Report
    # ══════════════════════════════════════════════════════════
    log.info("▶ STEP 3: Generating reports + rebuttals…")
    db.update_run(run_id, current_step=3)

    try:
        reports = step3_reporter.run(detections, config)
    except Exception as exc:
        log.error("Step 3 FAILED: %s", exc, exc_info=True)
        db.fail_run(run_id, step=3, error=str(exc))
        _start_next_pending()
        return None

    log.info("✓ Step 3 complete — %d reports generated", len(reports))

    for idx, report in enumerate(reports):
        slug    = _safe_filename(report["meta"].get("title", f"article_{idx}"))
        s3_path = f"runs/{run_id}/step3_reports/{slug}__{idx:04d}__report.json"
        s3_url  = upload_json(s3_path, report)
        db.insert_report(
            run_id,
            detection_id=detection_id_map.get(idx),
            report=report,
            storage_path=s3_url,
        )

    # ══════════════════════════════════════════════════════════
    #  COMPLETE
    # ══════════════════════════════════════════════════════════
    db.complete_run(
        run_id,
        step1=len(articles),
        step2=total_detections,
        step3=len(reports),
    )

    log.info("═" * 65)
    log.info("✅  Pipeline Run COMPLETE")
    log.info("    Run ID             : %s", run_id)
    log.info("    Articles scraped   : %d", len(articles))
    log.info("    Detections found   : %d", total_detections)
    log.info("    Reports generated  : %d", len(reports))
    log.info("    Storage prefix     : runs/%s/", run_id)
    log.info("═" * 65)

    _start_next_pending()
    return run_id


def _start_next_pending():
    pending = db.pop_pending()
    if pending:
        log.info("Starting queued pending run (triggered_by=%s)",
                 pending.get("triggered_by"))
        orchestrate(triggered_by=pending.get("triggered_by", "pending_queue"))


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

def main():
    active = db.get_active_run()
    if not active:
        pending = db.pop_pending()
        if pending:
            log.info("Resuming queued run on startup")
            orchestrate(triggered_by=pending.get("triggered_by", "startup_resume"))
            return
    orchestrate(triggered_by="manual")


if __name__ == "__main__":
    main()