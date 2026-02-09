"""Karate Feature File model for storing .feature files."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class KarateFeatureFile(Base):
    """Stored Karate .feature files for advanced BDD-style API testing."""
    __tablename__ = "karate_feature_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_collections.id"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The actual .feature file content (Gherkin syntax)
    feature_content: Mapped[str] = mapped_column(Text)

    # Parsed metadata (JSONB)
    # {
    #   feature_name: "...",
    #   feature_tags: ["@smoke", "@api"],
    #   scenarios: [{name, tags, line_number}],
    #   background: {steps: [...]},
    # }
    parsed_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Associated karate-config.js content (optional)
    config_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Additional Karate files (JSONB for storing helper functions, data files, etc.)
    # {filename: content}
    additional_files: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Tags for filtering/organizing features
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)

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
    collection: Mapped["APICollection | None"] = relationship("APICollection", back_populates="karate_features")
