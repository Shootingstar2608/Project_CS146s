"""
SQLAlchemy ORM models — PostgreSQL tables.

Lưu metadata tài liệu, lịch sử chat. Graph data nằm trong Neo4j.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, Enum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class cho tất cả ORM models."""
    pass


class Document(Base):
    """Bảng lưu metadata của mỗi file PDF đã upload."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    original_path = Column(String(500), nullable=True)
    status = Column(
        String(20),
        default="processing",
        comment="processing | completed | failed",
    )
    entity_count = Column(Integer, default=0)
    relation_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class ChatSession(Base):
    """Bảng lưu thông tin phiên chat."""

    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    """Bảng lưu lịch sử tin nhắn."""

    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, nullable=False, index=True)
    role = Column(String(20), nullable=False, comment="user | assistant")
    content = Column(Text, nullable=False)
    reasoning_steps = Column(Text, nullable=True, comment="JSON string of reasoning steps")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
