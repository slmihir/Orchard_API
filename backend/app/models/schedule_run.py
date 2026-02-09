import uuid
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.postgres import Base


class ScheduleRun(Base):
    """Tracks each execution of a schedule (collection-level run)."""
    __tablename__ = "schedule_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("schedules.id"))

    status: Mapped[str] = mapped_column(String(20))  # running, passed, failed
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Stats
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    schedule: Mapped["Schedule"] = relationship("Schedule", back_populates="runs")
    test_runs: Mapped[list["Run"]] = relationship("Run", back_populates="schedule_run")
