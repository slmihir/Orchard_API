"""API Environment model for environment-specific variable sets."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class APIEnvironment(Base):
    """Environment-specific variable sets for API testing."""
    __tablename__ = "api_environments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_collections.id"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(255))  # e.g., "Development", "Staging", "Production"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Environment variables (JSONB)
    # Structure: {var_name: {value: "...", type: "string|number|boolean", secret: false}}
    variables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Base URL override for this environment
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Auth config override for this environment
    auth_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Default headers override for this environment
    default_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Whether this is the default environment for the collection
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Multi-tenancy (environment can be collection-specific or global to tenant)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    collection: Mapped["APICollection | None"] = relationship("APICollection", back_populates="environments")
    test_runs: Mapped[list["APITestRun"]] = relationship("APITestRun", back_populates="environment")
