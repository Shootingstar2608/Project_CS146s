"""Redis-backed document ingestion event helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis

from app.config import get_settings


def document_channel(document_id: str) -> str:
    return f"document:{document_id}:events"


def publish_document_event(
    document_id: str,
    status: str,
    phase: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Publish one ingestion event so websocket clients can update live."""
    cfg = get_settings()
    payload = {
        "document_id": document_id,
        "status": status,
        "phase": phase,
        "message": message,
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    client = redis.Redis.from_url(cfg.redis_url, decode_responses=True)
    try:
        client.publish(document_channel(document_id), json.dumps(payload))
    finally:
        client.close()
