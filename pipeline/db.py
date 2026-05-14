"""
pipeline/db.py  — AWS RDS PostgreSQL, schema = dev (DB_SCHEMA env var)

Tables match the exact Supabase schema you shared:
  pipeline_runs, pipeline_logs, pipeline_config,
  scraped_articles, detections, reports,
  internal_documents
"""

import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras

log = logging.getLogger(__name__)

# ── Config from .env ─────────────────────────────────────────────────────────
_HOST     = os.environ["DB_HOST"]
_PORT     = int(os.environ.get("DB_PORT", "5432"))
_NAME     = os.environ["DB_NAME"]
_USER     = os.environ["DB_USER"]
_PASSWORD = os.environ["DB_PASSWORD"]
_SCHEMA   = os.environ.get("DB_SCHEMA", "dev")

# ── Connection ────────────────────────────────────────────────────────────────
def _connect():
    return psycopg2.connect(
        host=_HOST,
        port=_PORT,
        dbname=_NAME,
        user=_USER,
        password=_PASSWORD,
        options=f"-c search_path={_SCHEMA},public",
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


@contextmanager
def _cursor():
    """Yield a cursor; commit on success, rollback on error, always close."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# pipeline_runs
# Exact columns: id(uuid), created_at, started_at, finished_at, status,
#   current_step, step1_articles, step2_detections, step3_reports,
#   failed_step, error_message, config_snapshot, storage_prefix
# status CHECK: pending | started | running | complete | failed
# ══════════════════════════════════════════════════════════════════════════════

def create_run(run_id: str, config_snapshot: dict) -> None:
    sql = f"""
        INSERT INTO {_SCHEMA}.pipeline_runs
            (id, status, current_step, config_snapshot,
             storage_prefix, created_at)
        VALUES (%s, 'pending', 0, %s, %s, NOW())
    """
    storage_prefix = f"runs/{run_id}/"
    with _cursor() as cur:
        cur.execute(sql, (run_id, json.dumps(config_snapshot), storage_prefix))
    log.debug("Created run %s", run_id)


def update_run(run_id: str, **kwargs) -> None:
    """
    Update any columns on pipeline_runs.
    Accepted kwargs: status, current_step, step1_articles,
                     step2_detections, step3_reports,
                     failed_step, error_message,
                     started_at, finished_at, storage_prefix
    Note: column is  failed_step  (not failed_at_step)
          and        finished_at  (not completed_at / failed_at)
    """
    if not kwargs:
        return
    cols = ", ".join(f"{k} = %s" for k in kwargs)
    vals = list(kwargs.values()) + [run_id]
    sql  = f"UPDATE {_SCHEMA}.pipeline_runs SET {cols} WHERE id = %s"
    with _cursor() as cur:
        cur.execute(sql, vals)


def get_active_run() -> dict | None:
    sql = f"""
        SELECT * FROM {_SCHEMA}.pipeline_runs
        WHERE status IN ('pending', 'started', 'running')
        ORDER BY created_at ASC
        LIMIT 1
    """
    with _cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
    return dict(row) if row else None


def fail_run(run_id: str, step: int, error: str) -> None:
    update_run(
        run_id,
        status="failed",
        failed_step=step,            # exact column name from your schema
        error_message=error[:2000],
        finished_at=_now(),
    )


def complete_run(run_id: str, step1: int, step2: int, step3: int) -> None:
    update_run(
        run_id,
        status="complete",           # your schema CHECK uses 'complete' not 'completed'
        step1_articles=step1,
        step2_detections=step2,
        step3_reports=step3,
        finished_at=_now(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# pipeline_logs
# Exact columns: id(bigserial), run_id, created_at, level, step, message
# level CHECK: debug | info | warning | error
# ══════════════════════════════════════════════════════════════════════════════

def log_to_db(
    run_id: str,
    message: str,
    level: str = "info",
    step: int | None = None,
) -> None:
    if level not in ("debug", "info", "warning", "error"):
        level = "info"
    sql = f"""
        INSERT INTO {_SCHEMA}.pipeline_logs
            (run_id, level, step, message, created_at)
        VALUES (%s, %s, %s, %s, NOW())
    """
    try:
        with _cursor() as cur:
            cur.execute(sql, (run_id, level, step, message[:4000]))
    except Exception as exc:
        log.warning("log_to_db failed: %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
# scraped_articles  (your real table name — NOT 'articles')
# Exact columns: id(uuid), run_id, created_at, title, url(NOT NULL), site,
#   published_date, snippet, search_term, date_range, country,
#   scrape_status, scrape_method, failure_reason, content, storage_path
# ══════════════════════════════════════════════════════════════════════════════

def insert_article(run_id: str, article: dict, storage_path: str | None = None) -> str | None:
    art_id = str(uuid.uuid4())
    sql = f"""
        INSERT INTO {_SCHEMA}.scraped_articles
            (id, run_id, title, url, site,
             published_date, snippet, search_term, date_range,
             country, scrape_status, scrape_method, failure_reason,
             content, storage_path, created_at)
        VALUES
            (%s, %s, %s, %s, %s,
             %s, %s, %s, %s,
             %s, %s, %s, %s,
             %s, %s, NOW())
    """
    try:
        with _cursor() as cur:
            cur.execute(sql, (
                art_id,
                run_id,
                article.get("title", "")[:500],
                article.get("url", ""),                       # NOT NULL
                article.get("site") or article.get("domain") or article.get("source"),
                article.get("published_date") or article.get("published_at") or article.get("date"),
                article.get("snippet") or article.get("content", "")[:500],
                article.get("search_term"),
                article.get("date_range"),
                article.get("country"),
                article.get("scrape_status", "scraped"),
                article.get("scrape_method"),
                article.get("failure_reason"),
                article.get("content"),
                storage_path,
            ))
        return art_id
    except Exception as exc:
        log.error("insert_article failed: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# detections
# Exact columns: id(uuid), run_id, article_id, created_at, url, title, site,
#   published_date, status, skip_reason, total_detections,
#   strong_phobic, medium_phobic, weak_phobic,
#   authors(jsonb), detection_payload(jsonb), storage_path
# FK: article_id → scraped_articles(id)
# ══════════════════════════════════════════════════════════════════════════════

def insert_detection(
    run_id: str,
    article_id: str | None,
    detection: dict,
    storage_path: str | None = None,
) -> str | None:
    det_id  = str(uuid.uuid4())
    summary = detection.get("summary", {})
    sql = f"""
        INSERT INTO {_SCHEMA}.detections
            (id, run_id, article_id, url, title, site,
             published_date, status, skip_reason,
             total_detections, strong_phobic, medium_phobic, weak_phobic,
             authors, detection_payload, storage_path, created_at)
        VALUES
            (%s, %s, %s, %s, %s, %s,
             %s, %s, %s,
             %s, %s, %s, %s,
             %s, %s, %s, NOW())
    """
    try:
        with _cursor() as cur:
            cur.execute(sql, (
                det_id,
                run_id,
                article_id,
                detection.get("url"),
                detection.get("title"),
                detection.get("site") or detection.get("domain"),
                detection.get("published_date") or detection.get("published_at"),
                detection.get("status", "processed"),
                detection.get("skip_reason"),
                summary.get("total_detections", 0),
                summary.get("strong_phobic", 0),
                summary.get("medium_phobic", 0),
                summary.get("weak_phobic", 0),
                json.dumps(detection.get("authors")) if detection.get("authors") else None,
                json.dumps(detection),                        # full payload in detection_payload
                storage_path,
            ))
        return det_id
    except Exception as exc:
        log.error("insert_detection failed: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# reports
# Exact columns: id(uuid), run_id, detection_id, created_at, url, title, site,
#   authors(jsonb), final_score(float), executive_summary, qualitative_insight,
#   refs_count(int), report_payload(jsonb), storage_path
# FK: detection_id → detections(id), run_id → pipeline_runs(id)
# ══════════════════════════════════════════════════════════════════════════════

def insert_report(
    run_id: str,
    detection_id: str | None,
    report: dict,
    storage_path: str | None = None,
) -> str | None:
    rep_id = str(uuid.uuid4())
    meta   = report.get("meta", {})
    sql = f"""
        INSERT INTO {_SCHEMA}.reports
            (id, run_id, detection_id, url, title, site,
             authors, final_score, executive_summary, qualitative_insight,
             refs_count, report_payload, storage_path, created_at)
        VALUES
            (%s, %s, %s, %s, %s, %s,
             %s, %s, %s, %s,
             %s, %s, %s, NOW())
    """
    try:
        with _cursor() as cur:
            cur.execute(sql, (
                rep_id,
                run_id,
                detection_id,
                meta.get("url") or report.get("url"),
                meta.get("title") or report.get("title"),
                meta.get("site") or report.get("site"),
                json.dumps(report.get("authors")) if report.get("authors") else None,
                report.get("final_score") or report.get("score"),
                report.get("executive_summary"),
                report.get("qualitative_insight"),
                int(report.get("refs_count", 0)),
                json.dumps(report),                           # full payload in report_payload
                storage_path,
            ))
        return rep_id
    except Exception as exc:
        log.error("insert_report failed: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# pipeline_config
# Exact columns: id(bigserial), created_at, updated_at, key(unique text),
#                value(jsonb), description
# Stores config as key/value rows. main.py expects:
#   key='sites'        value=["thewire.in", ...]
#   key='date_ranges'  value=[["03/01/2024","03/31/2025"], ...]
#   key='search_terms' value=["RSS", ...]
#   key='country'      value="in"
# ══════════════════════════════════════════════════════════════════════════════

def load_pipeline_config() -> dict:
    config: dict[str, Any] = {
        "sites":        [],
        "date_ranges":  [],
        "search_terms": [],
        "country":      os.environ.get("COUNTRY", "in"),
    }
    try:
        with _cursor() as cur:
            cur.execute(f"SELECT key, value FROM {_SCHEMA}.pipeline_config")
            for row in cur.fetchall():
                k, v = row["key"], row["value"]
                if k in config:
                    config[k] = v   # psycopg2 RealDictCursor returns jsonb already parsed
    except Exception as exc:
        log.error("load_pipeline_config failed: %s", exc)
    return config


# ══════════════════════════════════════════════════════════════════════════════
# pending_runs
# Your schema has no separate pending_runs table.
# We implement the queue using pipeline_runs itself:
#   enqueue  → create a run with status='pending' and queued=true in snapshot
#   pop      → atomically claim the oldest such run → status='started'
# ══════════════════════════════════════════════════════════════════════════════

def enqueue_pending(triggered_by: str = "manual") -> None:
    run_id = str(uuid.uuid4())
    create_run(run_id, {"triggered_by": triggered_by, "queued": True})
    log.info("Enqueued pending run %s (triggered_by=%s)", run_id, triggered_by)


def pop_pending() -> dict | None:
    """
    Atomically claim the oldest queued-pending run,
    mark it 'started', and return it so orchestrate() can execute it.
    """
    sql = f"""
        UPDATE {_SCHEMA}.pipeline_runs
        SET    status = 'started', started_at = NOW()
        WHERE  id = (
            SELECT id FROM {_SCHEMA}.pipeline_runs
            WHERE  status = 'pending'
              AND  config_snapshot->>'queued' = 'true'
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *
    """
    with _cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
    return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════════════════
# internal_documents  (used by step3_reporter as fallback to INTERNAL_DOC_URL)
# Exact columns: id, uploaded_at, storage_path, bucket, filename,
#                size_bytes, is_active, notes
# Unique index ensures only one active row at a time.
# ══════════════════════════════════════════════════════════════════════════════

def get_active_internal_doc() -> dict | None:
    """Return the currently active internal document record (is_active=true)."""
    sql = f"""
        SELECT * FROM {_SCHEMA}.internal_documents
        WHERE is_active = TRUE
        LIMIT 1
    """
    try:
        with _cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
        return dict(row) if row else None
    except Exception as exc:
        log.error("get_active_internal_doc failed: %s", exc)
        return None