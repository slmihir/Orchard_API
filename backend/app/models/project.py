"""Project, DiscoveredPage, and PageConnection models for site discovery."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class Project(Base):
    """A website project to be explored and tested."""
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Credentials (stored encrypted in production)
    credentials: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Discovery status
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, discovering, paused, completed, failed
    discovery_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovery_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Discovery config
    max_depth: Mapped[int] = mapped_column(Integer, default=5)
    max_pages: Mapped[int] = mapped_column(Integer, default=100)

    # Stats (updated during discovery)
    pages_discovered: Mapped[int] = mapped_column(Integer, default=0)
    features_found: Mapped[int] = mapped_column(Integer, default=0)
    patterns_detected: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Multi-tenancy
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )

    # Relationships
    pages: Mapped[list["DiscoveredPage"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    connections: Mapped[list["PageConnection"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class DiscoveredPage(Base):
    """A page/state discovered during exploration."""
    __tablename__ = "discovered_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))

    # Page identity
    url: Mapped[str] = mapped_column(String(1000))
    path: Mapped[str] = mapped_column(String(500))  # URL path without domain
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Page classification
    page_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # form, list, detail, dashboard, login, etc.
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Main nav section it belongs to

    # State hash for deduplication
    state_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Visual
    screenshot_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Content analysis (basic extraction)
    forms_found: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # [{name, fields, action}]
    actions_found: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # [{text, selector, type}]
    inputs_found: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # [{name, type, placeholder}]
    tables_found: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # [{columns, row_actions, pagination}]

    # LLM-powered analysis (rich data for test generation)
    llm_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # Full PageAnalysis from LLM
    test_scenarios: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # Suggested test scenarios
    requires_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    required_permissions: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ['admin', 'editor', etc.]

    # Navigation to reach this page (from login)
    nav_steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # Recorded Playwright steps
    depth: Mapped[int] = mapped_column(Integer, default=0)  # Clicks from login

    # Pattern detection
    is_pattern_instance: Mapped[bool] = mapped_column(Boolean, default=False)
    pattern_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "product_detail"

    # Feature extraction
    is_feature: Mapped[bool] = mapped_column(Boolean, default=False)
    feature_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    feature_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Graph positioning (for visualization)
    graph_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    graph_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    graph_z: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="pages")
    outgoing_connections: Mapped[list["PageConnection"]] = relationship(
        back_populates="source_page",
        foreign_keys="PageConnection.source_page_id",
        cascade="all, delete-orphan"
    )
    incoming_connections: Mapped[list["PageConnection"]] = relationship(
        back_populates="target_page",
        foreign_keys="PageConnection.target_page_id",
        cascade="all, delete-orphan"
    )


class PageConnection(Base):
    """An edge in the navigation graph - how to get from one page to another."""
    __tablename__ = "page_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))

    source_page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("discovered_pages.id"))
    target_page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("discovered_pages.id"))

    # How to traverse this edge
    action_type: Mapped[str] = mapped_column(String(50))  # click, navigate, submit
    action_selector: Mapped[str | None] = mapped_column(String(500), nullable=True)
    action_text: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Button/link text

    # The recorded step
    step: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="connections")
    source_page: Mapped["DiscoveredPage"] = relationship(
        back_populates="outgoing_connections",
        foreign_keys=[source_page_id]
    )
    target_page: Mapped["DiscoveredPage"] = relationship(
        back_populates="incoming_connections",
        foreign_keys=[target_page_id]
    )
