"""
pipeline/step2_detector.py — with taxonomy enrichment
"""

import gc
import json
import logging
import re
import uuid

from pipeline.taxonomy import enrich_detection

log = logging.getLogger(__name__)

GEMINI_MODEL_NAME    = "gemini-2.5-pro"
TOKEN_BUDGET         = 15_000
CHARS_PER_TOKEN      = 4
SAFETY_MARGIN_TOKENS = 500
MAX_CHARS_PER_CHUNK  = (TOKEN_BUDGET - SAFETY_MARGIN_TOKENS) * CHARS_PER_TOKEN
CHARS_OVERLAP        = 800
SKIP_FAILURE_PATTERNS = ["total failure", "all tiers failed"]

SYSTEM_PROMPT = r"""
Objective: You are a specialized, advanced RSS Phobia Detector. Your sole function is to identify and exhaustively extract every instance of "RSS Phobia" from a given text. Be conservative — focus on explicit phobic language, not analytical statements.

Definition: "RSS Phobia" is irrational, obsessive, unsubstantiated hatred or fear of RSS/Hindutva/Sangh Parivar, beyond legitimate evidence-based criticism.

Category codes for method_code field:
A1,A2,A3,A4,A5,A6,A7,A7.1 | B8-B15.1 | C16-C24 | D25-D39 | E40-E48
F49-F51 | G52-G53 | H54-H56 | I57-I58 | J59-J60 | K61-K62 | L63
M64-M65 | N66-N67 | O68-O69 | P70-P71 | Q72-Q73

STRICT OUTPUT — ONLY valid JSON, no markdown:
{
  "document_id": "<string>",
  "summary": {"total_detections": 0, "strong_phobic": 0, "medium_phobic": 0, "weak_phobic": 0},
  "authors": ["name - Media House"],
  "detections": [
    {
      "id": "<uuid>",
      "sentence": "<exact phobic sentence>",
      "score": 3,
      "method_code": "<e.g. A3>",
      "method_name": "<short label>",
      "page": 1,
      "Topic_id": "N/A",
      "Topic_name": "N/A",
      "span_char_start": 0,
      "span_char_end": 0,
      "red_flag": true,
      "slur": false,
      "Reasoning": "<one-line why it matches>"
    }
  ]
}
Scoring: 1-3=Mild, 4-6=Moderate, 7-8=Severe, 9-10=Extreme.
strong_phobic=score>=7, medium_phobic=4-6, weak_phobic=1-3.
"""


def _init_gemini(api_key: str):
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except ImportError:
        raise ImportError("pip install google-genai")


def _should_skip(article: dict) -> tuple[bool, str]:
    body = (article.get("body") or "").lower()
    for pat in SKIP_FAILURE_PATTERNS:
        if pat in body:
            return True, f"scrape failure: {pat}"
    if len(article.get("body") or "") < 100:
        return True, "body too short"
    return False, ""


def _chunk_text(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = min(start + MAX_CHARS_PER_CHUNK, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - CHARS_OVERLAP
    return chunks


def _safe_parse_json(raw: str) -> dict | None:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _call_gemini(client, text: str, document_id: str) -> dict | None:
    from google.genai import types
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=f"DOCUMENT ID: {document_id}\n\nTEXT TO ANALYSE:\n{text}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.0,
                top_p=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
            ),
        )
        return _safe_parse_json(response.text)
    except Exception as exc:
        log.error("Gemini call failed for %s: %s", document_id, exc)
        return None


def _merge_chunk_results(chunks_results: list, document_id: str, article: dict) -> dict:
    merged_detections = []
    strong = medium = weak = 0

    for cr in chunks_results:
        if not cr:
            continue
        for det in cr.get("detections", []):
            det["id"] = str(uuid.uuid4())
            enrich_detection(det)          # ← taxonomy enrichment here
            merged_detections.append(det)
            score = int(det.get("score", 0))
            if score >= 7:
                strong += 1
            elif score >= 4:
                medium += 1
            else:
                weak += 1

    authors = next((cr["authors"] for cr in chunks_results if cr and cr.get("authors")), [])

    return {
        "document_id":    document_id,
        "title":          article.get("title", ""),
        "url":            article.get("url", ""),
        "site":           article.get("site", ""),
        "published_date": article.get("published_date", ""),
        "body":           article.get("body", ""),
        "search_term":    article.get("search_term", ""),
        "date_range":     article.get("date_range", ""),
        "scrape_status":  article.get("scrape_status", ""),
        "scrape_method":  article.get("scrape_method", ""),
        "authors":        authors,
        "summary": {
            "total_detections": len(merged_detections),
            "strong_phobic":    strong,
            "medium_phobic":    medium,
            "weak_phobic":      weak,
        },
        "detections": merged_detections,
    }


def run(articles: list[dict], config: dict) -> list[dict]:
    """
    Step 2 entry point.
    Returns list of detection dicts, one per article.
    Every detection hit is enriched with taxonomy fields:
      method_name_full, main_category_ids, main_category_names
    """
    import os
    gemini_key = config.get("gemini_key") or os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("gemini_key required in config or GEMINI_API_KEY env var")

    client     = _init_gemini(gemini_key)
    detections = []

    log.info("Step 2 — Detecting in %d articles", len(articles))

    for i, article in enumerate(articles, 1):
        doc_id = str(uuid.uuid4())
        log.info("[%d/%d] %s", i, len(articles), article.get("title", "")[:60])

        skip, reason = _should_skip(article)
        if skip:
            log.info("  Skip: %s", reason)
            detections.append({
                "document_id": doc_id,
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "site": article.get("site", ""),
                "published_date": article.get("published_date", ""),
                "body": article.get("body", ""),
                "search_term": article.get("search_term", ""),
                "date_range": article.get("date_range", ""),
                "scrape_status": article.get("scrape_status", ""),
                "scrape_method": article.get("scrape_method", ""),
                "authors": [],
                "status": "skipped",
                "skip_reason": reason,
                "summary": {"total_detections": 0, "strong_phobic": 0, "medium_phobic": 0, "weak_phobic": 0},
                "detections": [],
            })
            continue

        chunks        = _chunk_text(article.get("body", ""))
        chunk_results = []
        log.info("  %d chunk(s)", len(chunks))
        for ci, chunk_text in enumerate(chunks, 1):
            log.info("  chunk %d/%d", ci, len(chunks))
            chunk_results.append(_call_gemini(client, chunk_text, f"{doc_id}_c{ci}"))

        merged         = _merge_chunk_results(chunk_results, doc_id, article)
        merged["status"] = "processed"
        detections.append(merged)
        log.info("  → %d detections (s=%d m=%d w=%d)",
                 merged["summary"]["total_detections"],
                 merged["summary"]["strong_phobic"],
                 merged["summary"]["medium_phobic"],
                 merged["summary"]["weak_phobic"])
        gc.collect()

    total = sum(d["summary"]["total_detections"] for d in detections)
    log.info("Step 2 done — %d total detections", total)
    return detections
