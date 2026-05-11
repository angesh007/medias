"""
pipeline/storage.py

Thin wrapper around Supabase Storage SDK.
All file I/O in the pipeline goes through this module so
switching backends later only requires changing this file.
"""

import io
import json
import logging
import os
import requests

log = logging.getLogger(__name__)

SUPABASE_URL    = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY    = os.environ.get("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "rss")


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def upload_json(storage_path: str, data: dict) -> str:
    """
    Upload a dict as JSON to Supabase Storage.

    Args:
        storage_path: path inside the bucket, e.g. "runs/abc/step1/article_001.json"
        data:         dict to serialise and upload

    Returns:
        Public URL of the uploaded object (or empty string on failure).
    """
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{storage_path}"

    resp = requests.post(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        data=payload,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
        log.info("Uploaded → %s", public_url)
        return public_url
    else:
        log.error("Upload failed [%s] %s → %s", resp.status_code, storage_path, resp.text[:200])
        return ""


def download_bytes(storage_path: str) -> bytes:
    """Download raw bytes from Supabase Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{storage_path}"
    resp = requests.get(
        url,
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content


def download_json(storage_path: str) -> dict:
    """Download and parse a JSON file from Supabase Storage."""
    raw = download_bytes(storage_path)
    return json.loads(raw.decode("utf-8"))


def download_from_url(url: str) -> bytes:
    """Download from any public Supabase URL (used for the internal PDF doc)."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def list_folder(prefix: str) -> list[str]:
    """List object keys under a storage prefix."""
    url = f"{SUPABASE_URL}/storage/v1/object/list/{SUPABASE_BUCKET}"
    resp = requests.post(
        url,
        headers=_headers(),
        json={"prefix": prefix, "limit": 1000},
        timeout=30,
    )
    if resp.status_code == 200:
        return [obj["name"] for obj in resp.json()]
    return []
