"""API Request model for individual API test request definitions."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class APIRequest(Base):
    """Individual API request definition within a collection."""
    __tablename__ = "api_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_collections.id"), index=True
    )

    # Request metadata
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # HTTP request definition
    method: Mapped[str] = mapped_column(String(10))  # GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
    url_path: Mapped[str] = mapped_column(String(1000))  # Relative path or full URL

    # Request components (JSONB for flexibility)
    headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    query_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Body configuration
    # Structure: {type: "json"|"form"|"raw"|"graphql", content: ...}
    body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Assertions configuration (JSONB array)
    # [{type: "status"|"jsonpath"|"header"|"timing"|"schema"|"body_contains", config: {...}, name: "..."}]
    assertions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Variable extraction for chaining
    # [{name: "var_name", source: "jsonpath"|"header"|"body", path: "$.data.id"}]
    variable_extractions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Pre-request scripts (Python code or Karate expressions)
    pre_request_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    pre_request_script_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # python, karate

    # Post-response scripts
    post_response_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_response_script_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Execution engine preference: "python", "karate", or null (use collection default)
    engine: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Folder/grouping within collection (for organization)
    folder_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timeout in milliseconds (per-request override)
    timeout_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    collection: Mapped["APICollection"] = relationship("APICollection", back_populates="requests")
    results: Mapped[list["APIRequestResult"]] = relationship(
        "APIRequestResult", back_populates="request", cascade="all, delete-orphan"
    )
