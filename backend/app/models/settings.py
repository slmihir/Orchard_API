"""User settings model for configurable features like healing."""

import uuid
from datetime import datetime
from sqlalchemy import String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class UserSettings(Base):
    """User-specific settings for healing and other features."""
    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)

    # Healing settings
    healing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    healing_auto_approve: Mapped[bool] = mapped_column(Boolean, default=True)
    healing_auto_approve_threshold: Mapped[float] = mapped_column(Float, default=0.85)
    healing_mode: Mapped[str] = mapped_column(String(20), default="inline")  # inline, batch, both
    healing_provider: Mapped[str] = mapped_column(String(20), default="gemini")  # gemini, openai, anthropic

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
