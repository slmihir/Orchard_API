import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class Schedule(Base):
    """Scheduled test runs."""
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))

    # Can schedule either a single test OR all tests in a collection
    test_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tests.id"), nullable=True)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("collections.id"), nullable=True)

    # Frequency: hourly, daily, weekly, or cron expression
    frequency: Mapped[str] = mapped_column(String(50))  # hourly, daily, weekly, custom
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)  # For custom schedules

    # Timing
    run_at_hour: Mapped[int | None] = mapped_column(nullable=True)  # 0-23, for daily/weekly
    run_at_minute: Mapped[int | None] = mapped_column(nullable=True, default=0)  # 0-59
    run_on_days: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "1,2,3,4,5" for weekdays (0=Sun, 6=Sat)

    # State
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # passed, failed

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
    test: Mapped["Test"] = relationship("Test", foreign_keys=[test_id])
    collection: Mapped["Collection"] = relationship("Collection", foreign_keys=[collection_id])
    runs: Mapped[list["ScheduleRun"]] = relationship("ScheduleRun", back_populates="schedule")
