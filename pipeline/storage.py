"""
pipeline/storage.py  — AWS S3 replacement for Supabase Storage
Bucket : mediareport01   (arn:aws:s3:::mediareport01)
Schema  : all keys are prefixed with  dev/
          so  runs/{run_id}/step1_scraped/foo.json
          becomes  dev/runs/{run_id}/step1_scraped/foo.json
"""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

# ── Config from .env ────────────────────────────────────────────────────────
_BUCKET      = os.environ.get("S3_BUCKET_NAME", "mediareport01")
_REGION      = os.environ.get("AWS_REGION", "us-east-2")
_URL_EXPIRY  = int(os.environ.get("S3_URL_EXPIRY", "3600"))
_SCHEMA      = os.environ.get("DB_SCHEMA", "dev")          # used as S3 key prefix

# ── Boto3 client (credentials come from env: AWS_ACCESS_KEY_ID / SECRET) ───
def _client():
    return boto3.client(
        "s3",
        region_name=_REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )


def _prefixed(path: str) -> str:
    """Prepend the schema prefix (e.g. 'dev') to every S3 key."""
    # Avoid double-slash if path already starts with the prefix
    path = path.lstrip("/")
    if path.startswith(f"{_SCHEMA}/"):
        return path
    return f"{_SCHEMA}/{path}"


# ── Public API (same signatures as the old Supabase version) ────────────────

def upload_json(path: str, data: dict) -> str:
    """
    Upload a dict as JSON to S3.

    Args:
        path : relative key, e.g. "runs/{run_id}/step1_scraped/foo.json"
        data : dict to serialise

    Returns:
        A pre-signed HTTPS URL valid for S3_URL_EXPIRY seconds.
        main.py stores this URL in the DB as the storage_path.
    """
    key = _prefixed(path)
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

    try:
        _client().put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=body,
            ContentType="application/json",
        )
        log.debug("Uploaded s3://%s/%s", _BUCKET, key)
    except ClientError as exc:
        log.error("S3 upload failed for key %s: %s", key, exc)
        raise

    return generate_presigned_url(key)


def upload_bytes(path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Upload raw bytes to S3 (kept for any future use).

    Returns a pre-signed URL.
    """
    key = _prefixed(path)
    try:
        _client().put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        log.debug("Uploaded bytes s3://%s/%s", _BUCKET, key)
    except ClientError as exc:
        log.error("S3 upload (bytes) failed for key %s: %s", key, exc)
        raise

    return generate_presigned_url(key)


def download_json(path: str) -> dict:
    """
    Download and parse a JSON object from S3.
    path is the same relative key passed to upload_json.
    """
    key = _prefixed(path)
    try:
        resp = _client().get_object(Bucket=_BUCKET, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except ClientError as exc:
        log.error("S3 download failed for key %s: %s", key, exc)
        raise


def generate_presigned_url(key: str, expiry: int | None = None) -> str:
    """
    Generate a pre-signed GET URL for any S3 key.
    key may be a full prefixed key (dev/runs/…) or a relative one.
    """
    # If caller passes a raw relative path, prefix it
    if not key.startswith(f"{_SCHEMA}/"):
        key = _prefixed(key)

    expiry = expiry or _URL_EXPIRY
    try:
        url = _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": _BUCKET, "Key": key},
            ExpiresIn=expiry,
        )
        return url
    except ClientError as exc:
        log.error("Failed to generate pre-signed URL for %s: %s", key, exc)
        raise


def public_url(path: str) -> str:
    """
    Return the direct S3 HTTPS URL (only works if bucket/object is public).
    Use generate_presigned_url() for private objects.
    """
    key = _prefixed(path)
    return f"https://{_BUCKET}.s3.{_REGION}.amazonaws.com/{key}"