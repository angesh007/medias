"""
pipeline/step3_reporter.py

Refactored from report.py.
Key changes:
  - run(detections, config) -> list[dict]
  - taxonomy.py fully integrated for category mapping
  - Internal PDF fetched from Supabase URL (not local disk)
  - build_flat_refs() uses taxonomy functions identical to original report.py
"""

import gc
import io
import json
import logging
import os
import re
import time

import pdfplumber
import requests

from pipeline.taxonomy import (
    get_main_categories_for_code,
    get_main_category_name,
    CATEGORY_LOOKUP,
)

log = logging.getLogger(__name__)

# ── Gemini params ─────────────────────────────────────────────
GEMINI_MODEL_NAME  = "gemini-2.5-pro"
MAX_CHARS_INTERNAL = 120_000
BATCH_SIZE         = 5
INTER_BATCH_DELAY  = 2.0

REBUTTAL_SOURCES = [
    "https://www.rss.org", "https://www.archivesofrss.org",
    "https://www.rssfacts.org", "https://www.organiser.org",
    "https://www.panchjanya.com", "https://vskbharat.com",
    "https://www.sevabharati.org", "https://myind.net",
    "https://indiafacts.org", "https://swarajyamag.com",
    "https://www.pgurus.com", "https://www.hinduvivekkendra.com",
    "https://bharatmata.in", "https://www.vicharkendrabharat.com",
    "https://indiapolicyfoundation.org",
]

REBUTTAL_SYSTEM_PROMPT = f"""
You are an expert research analyst specialising in Indian socio-political history,
the Rashtriya Swayamsevak Sangh (RSS), Hindu nationalism, and inter-community
relations in India.

Your task is to write accurate, well-grounded rebuttals to specific claims or
accusations made against the RSS or its affiliated organisations.

You are given:
  1. A list of HIT TEXTS (numbered claims to rebut).
  2. INTERNAL DOCUMENT — an authoritative internal knowledge base about the RSS.
  3. Use Google Search to find current, primary-source evidence from:
     {", ".join(REBUTTAL_SOURCES)}

WRITING RULES:
  - Directly address each claim. Do not be vague or generic.
  - Ground every sentence in evidence from the internal doc or search results.
  - Be factual, measured, and academically credible.
  - Each rebuttal: 100-200 words.
  - Prioritise primary RSS sources over secondary commentary.

SOURCE ATTRIBUTION:
  Set "rebuttal_source" to ONE of:
    - "internal"   → internal doc was the primary basis
    - an exact URL → a specific verified web page

URL VALIDATION:
  - Provide only valid, working URLs. Do NOT fabricate article URLs.
  - If a specific article URL cannot be verified, use the base domain only.
  - Never return broken links.

OUTPUT FORMAT — ONLY a valid JSON array, same order as input. No markdown:
[
  {{"index": 0, "rebuttal": "...", "rebuttal_source": "..."}},
  {{"index": 1, "rebuttal": "...", "rebuttal_source": "..."}}
]
""".strip()


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _init_gemini(api_key: str):
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except ImportError:
        raise ImportError("pip install google-genai")


def _load_internal_pdf_from_url(url: str) -> str:
    """Download internal PDF from Supabase Storage URL and extract text."""
    if not url:
        log.warning("INTERNAL_DOC_URL not set — rebuttals lack internal doc context")
        return ""
    try:
        log.info("Fetching internal doc: %s", url)
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        parts = []
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        full = "\n".join(parts)
        log.info("Internal doc: %d chars (capped at %d)", len(full), MAX_CHARS_INTERNAL)
        return full[:MAX_CHARS_INTERNAL]
    except Exception as exc:
        log.error("Could not load internal PDF: %s", exc)
        return ""


def _dedup_sentences(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    seen, out = set(), []
    for s in sentences:
        k = s.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(s)
    return " ".join(out)


def _calculate_final_score(refs: list) -> float:
    if not refs:
        return 0.0
    scores    = [abs(r.get("score", 0)) for r in refs]
    raw       = max(scores) + (len(scores) - 1) * 0.25
    return round(min(raw, 10.0), 2)


def _safe_parse_json_array(raw: str) -> list | None:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    m = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


# ══════════════════════════════════════════════════════════════
#  TAXONOMY — build_flat_refs (ported directly from report.py)
# ══════════════════════════════════════════════════════════════

def build_flat_refs(detection: dict) -> tuple[list, dict]:
    """
    Convert detection dicts into the flat refs list that report.py used.
    Uses get_main_categories_for_code and get_main_category_name from taxonomy.py
    exactly as the original report.py did.

    Returns:
        refs       - flat list of ref objects (one per unique detection id)
        categories - {str(main_id): category_name} dict
    """
    ref_map    = {}
    categories = {}

    for det in detection.get("detections", []):
        ref_id   = str(det.get("id", ""))
        code     = det.get("method_code", "")
        main_ids = get_main_categories_for_code(code)

        for mid in main_ids:
            categories[str(mid)] = get_main_category_name(mid)

        # Use the taxonomy CATEGORY_LOOKUP for the full method name
        full_method_name = CATEGORY_LOOKUP.get(code, det.get("method_name", ""))

        if ref_id not in ref_map:
            ref_map[ref_id] = {
                "id":              ref_id,
                "text":            det.get("sentence", ""),
                "score":           int(det.get("score", 0)),
                "method_code":     code,
                "method_name":     det.get("method_name", ""),
                "method_name_full": full_method_name,
                "topic_id":        det.get("Topic_id", "N/A"),
                "topic_name":      det.get("Topic_name", "N/A"),
                "reasoning":       det.get("Reasoning", ""),
                "red_flag":        det.get("red_flag", False),
                "slur":            det.get("slur", False),
                # taxonomy enrichment already applied in step2
                "main_category_ids":   det.get("main_category_ids", main_ids),
                "main_category_names": det.get("main_category_names",
                                               [get_main_category_name(i) for i in main_ids]),
                "categories": list(main_ids),
            }
        else:
            existing = set(ref_map[ref_id]["categories"])
            existing.update(main_ids)
            ref_map[ref_id]["categories"] = sorted(existing)

    return list(ref_map.values()), categories


# ══════════════════════════════════════════════════════════════
#  REBUTTAL INJECTION
# ══════════════════════════════════════════════════════════════

def _inject_rebuttals(refs: list, client, internal_text: str, max_retries: int = 3) -> tuple[int, int]:
    """Batch Gemini calls to generate rebuttals. Returns (updated, skipped)."""
    from google.genai import types

    items   = [{"index": i, "ref_obj": r, "text": r.get("text", "").strip()}
               for i, r in enumerate(refs)]
    valid   = [it for it in items if it["text"]]
    invalid = [it for it in items if not it["text"]]

    for it in invalid:
        it["ref_obj"]["rebuttal"]        = "No rebuttal available"
        it["ref_obj"]["rebuttal_source"] = None

    updated = skipped = 0

    for batch_start in range(0, len(valid), BATCH_SIZE):
        batch    = valid[batch_start: batch_start + BATCH_SIZE]
        numbered = "\n\n".join(f"[{it['index']}] {it['text']}" for it in batch)
        prompt   = (
            f"INTERNAL DOCUMENT (excerpt):\n{internal_text[:30_000]}\n\n"
            f"HIT TEXTS TO REBUT:\n{numbered}"
        )

        result = None
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=GEMINI_MODEL_NAME,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=REBUTTAL_SYSTEM_PROMPT,
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                    ),
                )
                result = _safe_parse_json_array(response.text)
                if result:
                    break
            except Exception as exc:
                log.warning("Rebuttal batch attempt %d failed: %s", attempt + 1, exc)
                time.sleep(2 ** attempt)

        if result:
            result_map = {r["index"]: r for r in result}
            for it in batch:
                res = result_map.get(it["index"])
                if res:
                    it["ref_obj"]["rebuttal"]        = res["rebuttal"]
                    it["ref_obj"]["rebuttal_source"] = res["rebuttal_source"]
                    updated += 1
                    log.info("      ✓ ref[%d] source → %s", it["index"],
                             str(res["rebuttal_source"])[:70])
                else:
                    it["ref_obj"]["rebuttal"]        = "No rebuttal available"
                    it["ref_obj"]["rebuttal_source"] = None
                    skipped += 1
        else:
            for it in batch:
                it["ref_obj"]["rebuttal"]        = "No rebuttal available"
                it["ref_obj"]["rebuttal_source"] = None
            skipped += len(batch)

        time.sleep(INTER_BATCH_DELAY)

    return updated, skipped


# ══════════════════════════════════════════════════════════════
#  LLM SUMMARIES
# ══════════════════════════════════════════════════════════════

def _generate_executive_summary(detection: dict, refs: list, categories: dict, client) -> str:
    cat_hits = {
        name: [r["text"] for r in refs if int(cat_id) in r.get("categories", [])]
        for cat_id, name in categories.items()
    }
    prompt = f"""
You are a Senior Academic Auditor specializing in objective content analysis.

TASK: Write an Executive Summary (200-300 words) based on the RSS-phobic references
found in this article. Focus on what is wrong and the author's rhetorical behaviour.
Concise, factual, based solely on the provided information.

Article Title: {detection.get('title', '')}
Authors: {", ".join(detection.get("authors", []))}

CATEGORY VIOLATIONS:
{json.dumps(cat_hits, indent=2)}

BODY EXCERPT:
{(detection.get("body", ""))[:4000]}

RULES: Analytical tone. Start directly. No headers.
"""
    try:
        response = client.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt)
        return _dedup_sentences(response.text.strip())
    except Exception as exc:
        log.warning("Executive summary failed: %s", exc)
        return "Summary generation failed."


def _generate_qualitative_insight(texts: list, client) -> str:
    prompt = f"""You are analyzing rhetorical construction patterns in critical narratives.
Write a structured academic analysis (150-220 words). Cover: how the narrative is
constructed step-by-step, framing and labeling strategies, escalation patterns,
justification of exclusion or harm, fear amplification, tone.
Analytical neutrality. No bullet points. Max 220 words.

Texts:
{chr(10).join(texts[:6])}"""
    try:
        response = client.models.generate_content(model=GEMINI_MODEL_NAME, contents=prompt)
        return response.text.strip()
    except Exception as exc:
        log.warning("Qualitative insight failed: %s", exc)
        return "Qualitative insight could not be generated."


# ══════════════════════════════════════════════════════════════
#  PUBLIC INTERFACE
# ══════════════════════════════════════════════════════════════

def run(detections: list[dict], config: dict) -> list[dict]:
    """
    Step 3 entry point.

    Args:
        detections:  list of detection dicts from step2 (taxonomy-enriched).
        config:      dict with keys:
                       gemini_key       str (required)
                       internal_doc_url str (Supabase Storage public URL)

    Returns:
        List of final report dicts shaped identically to the original
        report.py Entity_with_rebuttal output, one per article.

    Report dict shape:
    {
        "meta": { title, url, site, published_date, authors, body },
        "category": "Media",
        "detection_summary": { total_detections, strong_phobic, ... },
        "executive_summary": { text, final_score },
        "qualitative_insight": "...",
        "refs": [ { id, text, score, method_code, method_name_full,
                    main_category_ids, main_category_names, categories,
                    topic_id, topic_name, reasoning, red_flag, slur,
                    rebuttal, rebuttal_source } ],
        "categories": { "1": "Negative Stereotyping of RSS", ... }
    }
    """
    gemini_key       = config.get("gemini_key") or os.environ.get("GEMINI_API_KEY")
    internal_doc_url = config.get("internal_doc_url") or os.environ.get(
        "INTERNAL_DOC_URL",
        "https://yfjhxoaklcjekwncpiih.supabase.co/storage/v1/object/public/rss/Internaldoc.docx.pdf",
    )

    if not gemini_key:
        raise ValueError("gemini_key required in config or GEMINI_API_KEY env var")

    client        = _init_gemini(gemini_key)
    internal_text = _load_internal_pdf_from_url(internal_doc_url)
    reports       = []

    log.info("Step 3 — Generating reports for %d detections", len(detections))

    for i, detection in enumerate(detections, 1):
        title = detection.get("title", "")[:60]
        log.info("[%d/%d] Reporting: %s", i, len(detections), title)

        # ── Build flat refs + category map using taxonomy ─────
        refs, categories = build_flat_refs(detection)
        log.info("  %d refs extracted, %d categories", len(refs), len(categories))

        final_score = _calculate_final_score(refs)

        if refs:
            # ── Executive summary ─────────────────────────────
            exec_text = _generate_executive_summary(detection, refs, categories, client)

            # ── Rebuttal injection ────────────────────────────
            log.info("  Generating rebuttals for %d refs (batch=%d)…", len(refs), BATCH_SIZE)
            updated, skipped = _inject_rebuttals(refs, client, internal_text)
            log.info("  Rebuttals: %d generated, %d skipped", updated, skipped)

            # ── Qualitative insight ───────────────────────────
            texts               = [r["text"] for r in refs if r.get("text")]
            qualitative_insight = (
                _generate_qualitative_insight(texts, client) if texts
                else "No textual data available."
            )
        else:
            exec_text           = "No phobic content detected in this article."
            qualitative_insight = "No phobic content detected."

        # ── Assemble final report (matches original report.py output) ──
        report = {
            "meta": {
                "title":          detection.get("title", ""),
                "url":            detection.get("url", ""),
                "site":           detection.get("site", ""),
                "published_date": detection.get("published_date", ""),
                "authors":        detection.get("authors", []),
                "body":           detection.get("body", ""),
            },
            "category": "Media",
            "detection_summary": detection.get("summary", {}),
            "executive_summary": {
                "text":        exec_text,
                "final_score": final_score,
            },
            "qualitative_insight": qualitative_insight,
            "refs":       refs,
            "categories": categories,
        }
        reports.append(report)
        log.info("  ✓ Score: %.2f", final_score)
        gc.collect()

    log.info("Step 3 done — %d reports generated", len(reports))
    return reports
