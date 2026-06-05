"""WebSocket endpoints for background job status events."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.core.database import get_session_factory
from app.core.job_events import document_channel
from app.models.db_models import Document

router = APIRouter(tags=["Jobs"])


async def _document_snapshot(document_id: str) -> dict:
    async with get_session_factory()() as session:
        doc = await session.get(Document, document_id)
        if not doc:
            return {
                "document_id": document_id,
                "status": "failed",
                "phase": "missing",
                "message": "Document record was not found.",
                "metadata": {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "document_id": document_id,
            "status": doc.status,
            "phase": doc.status,
            "message": doc.error_message or f"Document is {doc.status}.",
            "metadata": {
                "entity_count": doc.entity_count or 0,
                "relation_count": doc.relation_count or 0,
                "completed_at": doc.completed_at.isoformat() if doc.completed_at else None,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.websocket("/jobs/documents/{document_id}/events")
async def document_job_events(websocket: WebSocket, document_id: str) -> None:
    """Stream document ingestion events for one uploaded PDF."""
    await websocket.accept()
    cfg = get_settings()
    client = redis.Redis.from_url(cfg.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    try:
        await websocket.send_json({
            "document_id": document_id,
            "status": "processing",
            "phase": "connected",
            "message": "Connected to document processing events.",
            "metadata": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await pubsub.subscribe(document_channel(document_id))
        await websocket.send_json(await _document_snapshot(document_id))
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=25)
            if not message:
                await websocket.send_json({
                    "document_id": document_id,
                    "status": "heartbeat",
                    "phase": "heartbeat",
                    "message": "Still connected.",
                    "metadata": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                continue
            data = message.get("data")
            if isinstance(data, str):
                await websocket.send_json(json.loads(data))
    except WebSocketDisconnect:
        return
    finally:
        await pubsub.unsubscribe(document_channel(document_id))
        await pubsub.close()
        await client.close()
