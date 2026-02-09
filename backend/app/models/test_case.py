"""TestCase and TestRun models for test management."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class TestCase(Base):
    """A test case generated from discovered page analysis."""
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    page_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("discovered_pages.id"), nullable=True)

    # Test info
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The NLP instruction that creates this test
    instruction: Mapped[str] = mapped_column(Text)

    # Recorded steps from execution (JSON array)
    # [{"action": "click", "selector": "...", "value": "...", "screenshot": "..."}]
    steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Test type
    test_type: Mapped[str] = mapped_column(String(50), default="positive")  # positive, negative, edge

    # Source of the test
    source: Mapped[str] = mapped_column(String(50), default="suggested")  # suggested, custom, recorded

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, recording, ready, passing, failing

    # Last run info
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # passed, failed, error
    last_run_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # milliseconds
    last_run_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    runs: Mapped[list["TestRun"]] = relationship(back_populates="test_case", cascade="all, delete-orphan")


class TestRun(Base):
    """A single execution of a test case."""
    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_cases.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))

    # Run status
    status: Mapped[str] = mapped_column(String(50), default="queued")  # queued, running, passed, failed, error

    # Execution details
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # milliseconds

    # Results
    steps_completed: Mapped[int] = mapped_column(Integer, default=0)
    steps_total: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_step: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Logs and artifacts
    logs: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # Array of log entries
    screenshots: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # Array of screenshot URLs

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    test_case: Mapped["TestCase"] = relationship(back_populates="runs")
