from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import BaseModel, model_validator

from app.db.postgres import get_db
from app.models.schedule import Schedule
from app.models.schedule_run import ScheduleRun
from app.models.run import Run
from app.models.test import Test, TestVersion, Collection
from app.models.user import User
from app.services.scheduler import run_scheduled_test, run_scheduled_collection, calculate_next_run
from app.security import get_current_user
from app.utils.tenant import tenant_filter, set_tenant

router = APIRouter()


class ScheduleCreate(BaseModel):
    name: str
    test_id: UUID | None = None
    collection_id: UUID | None = None
    frequency: str  # hourly, daily, weekly, custom
    cron_expression: str | None = None
    run_at_hour: int | None = None
    run_at_minute: int | None = 0
    run_on_days: str | None = None  # "1,2,3,4,5" for weekdays
    enabled: bool = True

    @model_validator(mode='after')
    def validate_target(self):
        if not self.test_id and not self.collection_id:
            raise ValueError("Either test_id or collection_id must be provided")
        if self.test_id and self.collection_id:
            raise ValueError("Cannot specify both test_id and collection_id")
        return self


class ScheduleUpdate(BaseModel):
    name: str | None = None
    frequency: str | None = None
    cron_expression: str | None = None
    run_at_hour: int | None = None
    run_at_minute: int | None = None
    run_on_days: str | None = None
    enabled: bool | None = None


class ScheduleResponse(BaseModel):
    id: UUID
    name: str
    test_id: UUID | None
    test_name: str | None
    collection_id: UUID | None
    collection_name: str | None
    target_type: str  # "test" or "collection"
    frequency: str
    cron_expression: str | None
    run_at_hour: int | None
    run_at_minute: int | None
    run_on_days: str | None
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_run_status: str | None
    created_at: datetime

    class Config:
        from_attributes = True


def build_schedule_response(schedule: Schedule) -> ScheduleResponse:
    """Helper to build ScheduleResponse from Schedule model."""
    return ScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        test_id=schedule.test_id,
        test_name=schedule.test.name if schedule.test else None,
        collection_id=schedule.collection_id,
        collection_name=schedule.collection.name if schedule.collection else None,
        target_type="collection" if schedule.collection_id else "test",
        frequency=schedule.frequency,
        cron_expression=schedule.cron_expression,
        run_at_hour=schedule.run_at_hour,
        run_at_minute=schedule.run_at_minute,
        run_on_days=schedule.run_on_days,
        enabled=schedule.enabled,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        last_run_status=schedule.last_run_status,
        created_at=schedule.created_at,
    )


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all schedules for current user."""
    result = await db.execute(
        select(Schedule)
        .where(tenant_filter(Schedule, current_user))
        .options(selectinload(Schedule.test), selectinload(Schedule.collection))
        .order_by(Schedule.created_at.desc())
    )
    schedules = result.scalars().all()
    return [build_schedule_response(s) for s in schedules]


@router.post("", response_model=ScheduleResponse)
async def create_schedule(
    data: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new schedule."""
    if data.test_id:
        test_result = await db.execute(
            select(Test).where(Test.id == data.test_id, tenant_filter(Test, current_user))
        )
        test = test_result.scalar_one_or_none()
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")

    if data.collection_id:
        coll_result = await db.execute(
            select(Collection).where(Collection.id == data.collection_id, tenant_filter(Collection, current_user))
        )
        collection = coll_result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")

    schedule = Schedule(
        name=data.name,
        test_id=data.test_id,
        collection_id=data.collection_id,
        frequency=data.frequency,
        cron_expression=data.cron_expression,
        run_at_hour=data.run_at_hour,
        run_at_minute=data.run_at_minute,
        run_on_days=data.run_on_days,
        enabled=data.enabled,
    )
    set_tenant(schedule, current_user)

    # Calculate next run time
    schedule.next_run_at = calculate_next_run(schedule)

    db.add(schedule)
    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Schedule)
        .options(selectinload(Schedule.test), selectinload(Schedule.collection))
        .where(Schedule.id == schedule.id)
    )
    schedule = result.scalar_one()

    return build_schedule_response(schedule)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a schedule by ID."""
    result = await db.execute(
        select(Schedule)
        .where(Schedule.id == schedule_id, tenant_filter(Schedule, current_user))
        .options(selectinload(Schedule.test), selectinload(Schedule.collection))
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return build_schedule_response(schedule)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    data: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a schedule."""
    result = await db.execute(
        select(Schedule)
        .where(Schedule.id == schedule_id, tenant_filter(Schedule, current_user))
        .options(selectinload(Schedule.test), selectinload(Schedule.collection))
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if data.name is not None:
        schedule.name = data.name
    if data.frequency is not None:
        schedule.frequency = data.frequency
    if data.cron_expression is not None:
        schedule.cron_expression = data.cron_expression
    if data.run_at_hour is not None:
        schedule.run_at_hour = data.run_at_hour
    if data.run_at_minute is not None:
        schedule.run_at_minute = data.run_at_minute
    if data.run_on_days is not None:
        schedule.run_on_days = data.run_on_days
    if data.enabled is not None:
        schedule.enabled = data.enabled

    # Recalculate next run time
    schedule.next_run_at = calculate_next_run(schedule)

    await db.commit()
    await db.refresh(schedule)

    return build_schedule_response(schedule)


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a schedule."""
    result = await db.execute(
        select(Schedule).where(Schedule.id == schedule_id, tenant_filter(Schedule, current_user))
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await db.delete(schedule)
    await db.commit()

    return {"status": "deleted"}


@router.post("/{schedule_id}/toggle", response_model=ScheduleResponse)
async def toggle_schedule(
    schedule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle a schedule's enabled state."""
    result = await db.execute(
        select(Schedule)
        .where(Schedule.id == schedule_id, tenant_filter(Schedule, current_user))
        .options(selectinload(Schedule.test), selectinload(Schedule.collection))
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    schedule.enabled = not schedule.enabled

    if schedule.enabled:
        schedule.next_run_at = calculate_next_run(schedule)

    await db.commit()
    await db.refresh(schedule)

    return build_schedule_response(schedule)


async def _run_schedule_task(schedule_id: UUID):
    """Background task to run a schedule immediately."""
    from app.db.postgres import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Schedule)
            .options(selectinload(Schedule.test), selectinload(Schedule.collection))
            .where(Schedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()

        if not schedule:
            print(f"[Scheduler] Schedule {schedule_id} not found for run now")
            return

        try:
            if schedule.collection_id:
                success, message = await run_scheduled_collection(schedule)
            else:
                success, message = await run_scheduled_test(schedule)

            # Update schedule
            schedule.last_run_at = datetime.utcnow()
            schedule.last_run_status = "passed" if success else "failed"
            await db.commit()

            print(f"[Scheduler] Run Now completed for '{schedule.name}': {schedule.last_run_status}")

        except Exception as e:
            print(f"[Scheduler] Error in Run Now for '{schedule.name}': {e}")
            schedule.last_run_at = datetime.utcnow()
            schedule.last_run_status = "failed"
            await db.commit()


@router.post("/{schedule_id}/run", response_model=ScheduleResponse)
async def run_schedule_now(
    schedule_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Run a schedule immediately (triggers test execution in background)."""
    result = await db.execute(
        select(Schedule)
        .where(Schedule.id == schedule_id, tenant_filter(Schedule, current_user))
        .options(selectinload(Schedule.test), selectinload(Schedule.collection))
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Queue the run in background
    background_tasks.add_task(_run_schedule_task, schedule_id)

    return build_schedule_response(schedule)


# Schedule Run History schemas
class TestRunResponse(BaseModel):
    id: UUID
    test_id: UUID
    test_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    error_message: str | None

    class Config:
        from_attributes = True


class ScheduleRunResponse(BaseModel):
    id: UUID
    schedule_id: UUID
    schedule_name: str
    target_type: str
    target_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_message: str | None
    test_runs: list[TestRunResponse] | None = None

    class Config:
        from_attributes = True


@router.get("/{schedule_id}/runs", response_model=list[ScheduleRunResponse])
async def get_schedule_runs(
    schedule_id: UUID,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get run history for a specific schedule."""
    schedule_result = await db.execute(
        select(Schedule)
        .where(Schedule.id == schedule_id, tenant_filter(Schedule, current_user))
        .options(selectinload(Schedule.test), selectinload(Schedule.collection))
    )
    schedule = schedule_result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    result = await db.execute(
        select(ScheduleRun)
        .where(ScheduleRun.schedule_id == schedule_id)
        .order_by(ScheduleRun.started_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()

    target_type = "collection" if schedule.collection_id else "test"
    target_name = schedule.collection.name if schedule.collection else (schedule.test.name if schedule.test else "Unknown")

    return [
        ScheduleRunResponse(
            id=run.id,
            schedule_id=run.schedule_id,
            schedule_name=schedule.name,
            target_type=target_type,
            target_name=target_name,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            duration_ms=int((run.finished_at - run.started_at).total_seconds() * 1000) if run.finished_at else None,
            total_tests=run.total_tests,
            passed_tests=run.passed_tests,
            failed_tests=run.failed_tests,
            error_message=run.error_message,
        )
        for run in runs
    ]


@router.get("/{schedule_id}/runs/{run_id}", response_model=ScheduleRunResponse)
async def get_schedule_run_detail(
    schedule_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get details of a specific schedule run including individual test runs."""
    schedule_result = await db.execute(
        select(Schedule)
        .where(Schedule.id == schedule_id, tenant_filter(Schedule, current_user))
        .options(selectinload(Schedule.test), selectinload(Schedule.collection))
    )
    schedule = schedule_result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    run_result = await db.execute(
        select(ScheduleRun)
        .where(ScheduleRun.id == run_id)
        .where(ScheduleRun.schedule_id == schedule_id)
    )
    schedule_run = run_result.scalar_one_or_none()
    if not schedule_run:
        raise HTTPException(status_code=404, detail="Schedule run not found")

    # Get individual test runs
    test_runs_result = await db.execute(
        select(Run, Test.name.label("test_name"), Test.id.label("test_id"))
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(Run.schedule_run_id == run_id)
        .order_by(Run.started_at)
    )
    test_runs_data = test_runs_result.all()

    target_type = "collection" if schedule.collection_id else "test"
    target_name = schedule.collection.name if schedule.collection else (schedule.test.name if schedule.test else "Unknown")

    test_runs = [
        TestRunResponse(
            id=run.id,
            test_id=test_id,
            test_name=test_name,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            duration_ms=int((run.finished_at - run.started_at).total_seconds() * 1000) if run.finished_at else None,
            error_message=run.error_message,
        )
        for run, test_name, test_id in test_runs_data
    ]

    return ScheduleRunResponse(
        id=schedule_run.id,
        schedule_id=schedule_run.schedule_id,
        schedule_name=schedule.name,
        target_type=target_type,
        target_name=target_name,
        status=schedule_run.status,
        started_at=schedule_run.started_at,
        finished_at=schedule_run.finished_at,
        duration_ms=int((schedule_run.finished_at - schedule_run.started_at).total_seconds() * 1000) if schedule_run.finished_at else None,
        total_tests=schedule_run.total_tests,
        passed_tests=schedule_run.passed_tests,
        failed_tests=schedule_run.failed_tests,
        error_message=schedule_run.error_message,
        test_runs=test_runs,
    )
