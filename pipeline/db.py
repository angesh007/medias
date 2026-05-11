"""
pipeline/db.py

Single Supabase database client for the entire pipeline.
Writes to all 7 tables defined in your SQL schema:
  pipeline_runs, pipeline_logs, scraped_articles,
  detections, reports, pipeline_config, internal_documents

All functions are safe to call from main.py and the step modules.
Errors are logged but never re-raised so a DB write failure never
crashes the pipeline itself.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("pipeline.db")

# ── lazy Supabase client (initialised once) ───────────────────
_client = None


def _sb():
    """Return (and lazily initialise) the Supabase client."""
    global _client
    if _client is None:
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(fn, *args, **kwargs):
    """Call fn; on any exception log and return None (never crash pipeline)."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        log.error("Supabase write failed: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════
#  pipeline_runs
# ══════════════════════════════════════════════════════════════

def create_run(run_id: str, config_snapshot: dict) -> dict | None:
    """Insert a new pipeline_runs row. Returns the inserted row."""
    row = {
        "id":              run_id,
        "started_at":      _now(),
        "status":          "started",
        "current_step":    0,
        "config_snapshot": config_snapshot,
        "storage_prefix":  f"runs/{run_id}/",
    }
    def _insert():
        return _sb().table("pipeline_runs").insert(row).execute()
    res = _safe(_insert)
    return res.data[0] if res and res.data else None


def update_run(run_id: str, **fields) -> None:
    """Partial-update a pipeline_runs row."""
    def _update():
        return _sb().table("pipeline_runs").update(fields).eq("id", run_id).execute()
    _safe(_update)


def complete_run(run_id: str, step1: int, step2: int, step3: int) -> None:
    update_run(
        run_id,
        status="complete",
        current_step=3,
        finished_at=_now(),
        step1_articles=step1,
        step2_detections=step2,
        step3_reports=step3,
    )


def fail_run(run_id: str, step: int, error: str) -> None:
    update_run(
        run_id,
        status="failed",
        finished_at=_now(),
        failed_step=step,
        error_message=error[:2000],
    )


def get_active_run() -> dict | None:
    """Return the first run with status 'running' or 'started', or None."""
    def _fetch():
        return (
            _sb()
            .table("pipeline_runs")
            .select("*")
            .in_("status", ["running", "started"])
            .limit(1)
            .execute()
        )
    res = _safe(_fetch)
    if res and res.data:
        return res.data[0]
    return None


def get_recent_runs(limit: int = 20) -> list[dict]:
    def _fetch():
        return (
            _sb()
            .table("pipeline_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    res = _safe(_fetch)
    return res.data if res and res.data else []


# ══════════════════════════════════════════════════════════════
#  pipeline_logs
# ══════════════════════════════════════════════════════════════

def log_to_db(run_id: str, message: str, level: str = "info", step: int | None = None) -> None:
    """Write one log line to pipeline_logs."""
    row = {
        "run_id":  run_id,
        "level":   level,
        "message": message[:4000],
    }
    if step is not None:
        row["step"] = step
    def _insert():
        return _sb().table("pipeline_logs").insert(row).execute()
    _safe(_insert)


def get_run_logs(run_id: str, limit: int = 500) -> list[dict]:
    def _fetch():
        return (
            _sb()
            .table("pipeline_logs")
            .select("*")
            .eq("run_id", run_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
    res = _safe(_fetch)
    return res.data if res and res.data else []


# ══════════════════════════════════════════════════════════════
#  scraped_articles
# ══════════════════════════════════════════════════════════════

def insert_article(run_id: str, article: dict, storage_path: str = "") -> str | None:
    """
    Insert one scraped article row.
    Returns the new UUID from Supabase, or None on failure.
    """
    row = {
        "run_id":         run_id,
        "title":          article.get("title", ""),
        "url":            article.get("url", ""),
        "site":           article.get("site", ""),
        "published_date": article.get("published_date", ""),
        "snippet":        article.get("snippet", ""),
        "search_term":    article.get("search_term", ""),
        "date_range":     article.get("date_range", ""),
        "country":        article.get("country", ""),
        "scrape_status":  article.get("scrape_status", ""),
        "scrape_method":  article.get("scrape_method", ""),
        "failure_reason": article.get("failure_reason"),
        "content":        (article.get("body") or "")[:100_000],  # cap at 100k chars
        "storage_path":   storage_path,
    }
    def _insert():
        return _sb().table("scraped_articles").insert(row).execute()
    res = _safe(_insert)
    if res and res.data:
        return res.data[0]["id"]
    return None


# ══════════════════════════════════════════════════════════════
#  detections
# ══════════════════════════════════════════════════════════════

def insert_detection(
    run_id: str,
    article_id: str | None,
    detection: dict,
    storage_path: str = "",
) -> str | None:
    """
    Insert one detection row.
    detection is the merged dict from step2_detector.run().
    Returns the new UUID or None.
    """
    summary = detection.get("summary", {})

    # Store full detection payload as JSONB (detections list + summary)
    payload = {
        "summary":    summary,
        "detections": detection.get("detections", []),
        "authors":    detection.get("authors", []),
    }

    row = {
        "run_id":            run_id,
        "article_id":        article_id,
        "url":               detection.get("url", ""),
        "title":             detection.get("title", ""),
        "site":              detection.get("site", ""),
        "published_date":    detection.get("published_date", ""),
        "status":            detection.get("status", "processed"),
        "skip_reason":       detection.get("skip_reason"),
        "total_detections":  summary.get("total_detections", 0),
        "strong_phobic":     summary.get("strong_phobic", 0),
        "medium_phobic":     summary.get("medium_phobic", 0),
        "weak_phobic":       summary.get("weak_phobic", 0),
        "authors":           detection.get("authors", []),
        "detection_payload": payload,
        "storage_path":      storage_path,
    }
    def _insert():
        return _sb().table("detections").insert(row).execute()
    res = _safe(_insert)
    if res and res.data:
        return res.data[0]["id"]
    return None


# ══════════════════════════════════════════════════════════════
#  reports
# ══════════════════════════════════════════════════════════════

def insert_report(
    run_id: str,
    detection_id: str | None,
    report: dict,
    storage_path: str = "",
) -> str | None:
    """
    Insert one report row.
    report is the dict from step3_reporter.run().
    Returns the new UUID or None.
    """
    meta    = report.get("meta", {})
    exec_s  = report.get("executive_summary", {})
    refs    = report.get("refs", [])

    row = {
        "run_id":              run_id,
        "detection_id":        detection_id,
        "url":                 meta.get("url", ""),
        "title":               meta.get("title", ""),
        "site":                meta.get("site", ""),
        "authors":             meta.get("authors", []),
        "final_score":         exec_s.get("final_score"),
        "executive_summary":   exec_s.get("text", ""),
        "qualitative_insight": report.get("qualitative_insight", ""),
        "refs_count":          len(refs),
        "report_payload":      report,   # full JSON stored as JSONB
        "storage_path":        storage_path,
    }
    def _insert():
        return _sb().table("reports").insert(row).execute()
    res = _safe(_insert)
    if res and res.data:
        return res.data[0]["id"]
    return None


# ══════════════════════════════════════════════════════════════
#  pipeline_config
# ══════════════════════════════════════════════════════════════

def get_config(key: str, default: Any = None) -> Any:
    """
    Fetch one config value from pipeline_config by key.
    The value column is JSONB so it's already parsed by supabase-py.
    """
    def _fetch():
        return (
            _sb()
            .table("pipeline_config")
            .select("value")
            .eq("key", key)
            .single()
            .execute()
        )
    res = _safe(_fetch)
    if res and res.data:
        return res.data["value"]
    return default


def set_config(key: str, value: Any, description: str = "") -> None:
    """Upsert a config value."""
    row = {"key": key, "value": value}
    if description:
        row["description"] = description
    def _upsert():
        return _sb().table("pipeline_config").upsert(row, on_conflict="key").execute()
    _safe(_upsert)


def load_pipeline_config() -> dict:
    """
    Load all pipeline_config rows and return as a flat dict.
    Falls back to env vars when a key is missing from the DB.
    """
    def _fetch():
        return _sb().table("pipeline_config").select("key,value").execute()
    res = _safe(_fetch)
    rows = res.data if res and res.data else []
    cfg  = {r["key"]: r["value"] for r in rows}

    # Merge with env-var secrets (never stored in DB)
    cfg["serper_key"]       = os.environ.get("SERPER_API_KEY", "")
    cfg["gemini_key"]       = os.environ.get("GEMINI_API_KEY", "")
    cfg["brightdata_wss"]   = os.environ.get("BRIGHTDATA_WSS", "")
    cfg["internal_doc_url"] = os.environ.get(
        "INTERNAL_DOC_URL",
        "https://yfjhxoaklcjekwncpiih.supabase.co/storage/v1/object/public/rss/Internaldoc.docx.pdf",
    )

    # Normalise types expected by step modules
    if isinstance(cfg.get("sites"), list):
        pass  # already a list from JSONB
    else:
        cfg["sites"] = ["thewire.in", "scroll.in", "ndtv.com"]

    if isinstance(cfg.get("date_ranges"), list):
        # Stored as [["MM/DD/YYYY","MM/DD/YYYY"], ...]
        cfg["date_ranges"] = [tuple(dr) for dr in cfg["date_ranges"]]
    else:
        cfg["date_ranges"] = [("03/01/2024", "03/31/2025")]

    if isinstance(cfg.get("search_terms"), list):
        pass
    else:
        cfg["search_terms"] = ["RSS", "Rashtriya Swayamsevak Sangh"]

    cfg.setdefault("country",              os.environ.get("COUNTRY", "in"))
    cfg.setdefault("max_results_per_site", int(os.environ.get("MAX_RESULTS_PER_SITE", 50)))
    cfg.setdefault("delay_between_sites",  2.0)
    cfg.setdefault("delay_between_articles", 1.5)
    cfg.setdefault("min_content_length",   300)
    cfg.setdefault("use_tier1", True)
    cfg.setdefault("use_tier2", True)
    cfg.setdefault("use_tier3", True)
    cfg.setdefault("use_tier4", bool(os.environ.get("BRIGHTDATA_WSS")))

    return cfg


# ══════════════════════════════════════════════════════════════
#  pending_runs queue  (stored in pipeline_config key='pending_runs')
# ══════════════════════════════════════════════════════════════

def enqueue_pending(triggered_by: str = "manual") -> None:
    """Push a pending run entry onto the queue in pipeline_config."""
    queue: list = get_config("pending_runs", []) or []
    queue.append({"triggered_by": triggered_by, "queued_at": _now()})
    set_config("pending_runs", queue)
    log.info("Enqueued pending run (triggered_by=%s). Queue length: %d", triggered_by, len(queue))


def pop_pending() -> dict | None:
    """Pop (FIFO) the oldest pending run from the queue. Returns it or None."""
    queue: list = get_config("pending_runs", []) or []
    if not queue:
        return None
    item  = queue.pop(0)
    set_config("pending_runs", queue)
    return item


# ══════════════════════════════════════════════════════════════
#  internal_documents
# ══════════════════════════════════════════════════════════════

def register_internal_doc(storage_path: str, filename: str, size_bytes: int = 0) -> None:
    """
    Mark a new internal document as active (deactivates any previous one).
    Call this after you manually upload a new Internaldoc to Supabase Storage.
    """
    def _deactivate():
        return (
            _sb()
            .table("internal_documents")
            .update({"is_active": False})
            .eq("is_active", True)
            .execute()
        )
    _safe(_deactivate)

    row = {
        "storage_path": storage_path,
        "bucket":       os.environ.get("SUPABASE_BUCKET", "rss"),
        "filename":     filename,
        "size_bytes":   size_bytes,
        "is_active":    True,
    }
    def _insert():
        return _sb().table("internal_documents").insert(row).execute()
    _safe(_insert)
