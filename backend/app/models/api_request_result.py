"""API Request Result model for detailed execution results."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class APIRequestResult(Base):
    """Detailed result for each request in a test run."""
    __tablename__ = "api_request_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_test_runs.id"), index=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_requests.id"), index=True
    )

    # Execution order in the run
    execution_order: Mapped[int] = mapped_column(Integer)

    # Status
    status: Mapped[str] = mapped_column(String(50))  # passed, failed, skipped, error

    # Request details (captured at execution time with resolved variables)
    resolved_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    resolved_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    resolved_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolved_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Response details
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)  # Truncated if too large
    response_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Detailed timing breakdown (JSONB)
    # {dns_ms, connect_ms, tls_ms, ttfb_ms, download_ms}
    timing_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Assertion results (JSONB array)
    # [{type, name, passed, expected, actual, message}]
    assertion_results: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Extracted variables (JSONB)
    # {var_name: extracted_value}
    extracted_variables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Error details
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # timeout, connection, assertion, script

    # Pre/post script execution info
    pre_script_executed: Mapped[bool | None] = mapped_column(nullable=True)
    pre_script_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_script_executed: Mapped[bool | None] = mapped_column(nullable=True)
    post_script_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    test_run: Mapped["APITestRun"] = relationship("APITestRun", back_populates="results")
    request: Mapped["APIRequest"] = relationship("APIRequest", back_populates="results")
