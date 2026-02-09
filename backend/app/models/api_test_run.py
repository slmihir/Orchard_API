"""API Test Run model for execution records."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class APITestRun(Base):
    """Execution record for API test runs."""
    __tablename__ = "api_test_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_collections.id"), nullable=True, index=True
    )

    # Run metadata
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Trigger source
    trigger_type: Mapped[str] = mapped_column(String(50))  # manual, scheduled, ci, webhook
    trigger_source: Mapped[str | None] = mapped_column(String(255), nullable=True)  # CI job ID, schedule ID, etc.

    # Environment used
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_environments.id"), nullable=True
    )

    # Execution engine used
    engine: Mapped[str] = mapped_column(String(20), default="python")  # python, karate

    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, running, passed, failed, error, cancelled

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Summary stats
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    passed_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)
    skipped_requests: Mapped[int] = mapped_column(Integer, default=0)

    # Total assertions
    total_assertions: Mapped[int] = mapped_column(Integer, default=0)
    passed_assertions: Mapped[int] = mapped_column(Integer, default=0)
    failed_assertions: Mapped[int] = mapped_column(Integer, default=0)

    # Error details (for run-level errors)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Runtime context (JSONB for variable snapshots, execution options, etc.)
    run_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Karate-specific: job ID for tracking in Redis queue
    karate_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Multi-tenancy
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    collection: Mapped["APICollection | None"] = relationship("APICollection", back_populates="test_runs")
    environment: Mapped["APIEnvironment | None"] = relationship("APIEnvironment", back_populates="test_runs")
    results: Mapped[list["APIRequestResult"]] = relationship(
        "APIRequestResult", back_populates="test_run", cascade="all, delete-orphan"
    )
