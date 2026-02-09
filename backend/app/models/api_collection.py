"""API Collection model for organizing API test requests."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class APICollection(Base):
    """Collection of API requests with shared configuration."""
    __tablename__ = "api_collections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Base configuration
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Authentication configuration (JSONB for flexibility)
    # Structure: {type: "bearer"|"basic"|"api_key"|"oauth2", config: {...}}
    auth_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Collection-level variables (JSONB)
    # Structure: {var_name: {value: "...", type: "string|number|boolean"}}
    variables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Default headers for all requests in collection
    default_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Default execution engine: "python" or "karate"
    default_engine: Mapped[str] = mapped_column(String(20), default="python")

    # Import source tracking
    import_source: Mapped[str | None] = mapped_column(String(50), nullable=True)  # postman, openapi, karate, manual
    import_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Original file/collection ID

    # Multi-tenancy
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    requests: Mapped[list["APIRequest"]] = relationship(
        "APIRequest", back_populates="collection", cascade="all, delete-orphan"
    )
    environments: Mapped[list["APIEnvironment"]] = relationship(
        "APIEnvironment", back_populates="collection", cascade="all, delete-orphan"
    )
    test_runs: Mapped[list["APITestRun"]] = relationship(
        "APITestRun", back_populates="collection", cascade="all, delete-orphan"
    )
    karate_features: Mapped[list["KarateFeatureFile"]] = relationship(
        "KarateFeatureFile", back_populates="collection", cascade="all, delete-orphan"
    )
