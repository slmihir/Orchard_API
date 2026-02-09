"""Database model for healing suggestions."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class HealingSuggestion(Base):
    """Stores healing suggestions for failed test steps."""
    __tablename__ = "healing_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id"))
    step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("steps.id"))
    step_index: Mapped[int] = mapped_column(Integer)

    # Original vs suggested
    original_selector: Mapped[str] = mapped_column(String(500))
    suggested_selector: Mapped[str] = mapped_column(String(500))
    alternative_selectors: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # LLM analysis
    confidence: Mapped[float] = mapped_column(Float)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    selector_type: Mapped[str] = mapped_column(String(20), default="css")  # css, xpath, text

    # Context snapshot (for debugging/review)
    context_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    screenshot_b64: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status: pending, approved, rejected, auto_applied
    status: Mapped[str] = mapped_column(String(20), default="pending")
    auto_approved: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Result after applying (if retried)
    retry_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
