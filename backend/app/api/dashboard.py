from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from pydantic import BaseModel
from uuid import UUID

from app.db.postgres import get_db
from app.models.test import Test, TestVersion, Step, Collection
from app.models.run import Run
from app.models.user import User
from app.security import get_current_user
from app.utils.tenant import tenant_filter


router = APIRouter()


class DashboardStats(BaseModel):
    total_tests: int
    total_runs: int
    runs_today: int
    pass_rate: float
    passed_runs: int
    failed_runs: int


class RecentRun(BaseModel):
    id: UUID
    test_id: UUID
    test_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    collection_name: str | None
    collection_color: str | None


class RunListResponse(BaseModel):
    id: UUID
    test_id: UUID
    test_name: str
    version_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    duration_ms: int | None
    collection_name: str | None
    collection_color: str | None


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics for current user."""
    # Total tests for this user
    total_tests_result = await db.execute(
        select(func.count(Test.id)).where(tenant_filter(Test, current_user))
    )
    total_tests = total_tests_result.scalar() or 0

    # Base query for runs: only count runs for user's tests
    user_runs_subquery = (
        select(Run.id)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(tenant_filter(Test, current_user))
    ).subquery()

    # Total runs for user's tests
    total_runs_result = await db.execute(
        select(func.count()).select_from(user_runs_subquery)
    )
    total_runs = total_runs_result.scalar() or 0

    # Runs today for user's tests
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    runs_today_result = await db.execute(
        select(func.count(Run.id))
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(tenant_filter(Test, current_user), Run.started_at >= today_start)
    )
    runs_today = runs_today_result.scalar() or 0

    # Pass/fail counts for user's tests
    passed_result = await db.execute(
        select(func.count(Run.id))
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(tenant_filter(Test, current_user), Run.status == 'passed')
    )
    passed_runs = passed_result.scalar() or 0

    failed_result = await db.execute(
        select(func.count(Run.id))
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(tenant_filter(Test, current_user), Run.status == 'failed')
    )
    failed_runs = failed_result.scalar() or 0

    # Calculate pass rate
    completed_runs = passed_runs + failed_runs
    pass_rate = (passed_runs / completed_runs * 100) if completed_runs > 0 else 0

    return DashboardStats(
        total_tests=total_tests,
        total_runs=total_runs,
        runs_today=runs_today,
        pass_rate=round(pass_rate, 1),
        passed_runs=passed_runs,
        failed_runs=failed_runs,
    )


@router.get("/recent-runs", response_model=list[RecentRun])
async def get_recent_runs(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get recent test runs for current user."""
    query = (
        select(Run, Test, TestVersion, Collection)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .outerjoin(Collection, Test.collection_id == Collection.id)
        .where(tenant_filter(Test, current_user))
        .order_by(Run.started_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        RecentRun(
            id=run.id,
            test_id=test.id,
            test_name=test.name,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error_message=run.error_message,
            collection_name=collection.name if collection else None,
            collection_color=collection.color if collection else None,
        )
        for run, test, version, collection in rows
    ]


@router.get("/recent-failures", response_model=list[RecentRun])
async def get_recent_failures(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get recent failed runs for current user."""
    query = (
        select(Run, Test, TestVersion, Collection)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .outerjoin(Collection, Test.collection_id == Collection.id)
        .where(tenant_filter(Test, current_user), Run.status == 'failed')
        .order_by(Run.started_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        RecentRun(
            id=run.id,
            test_id=test.id,
            test_name=test.name,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error_message=run.error_message,
            collection_name=collection.name if collection else None,
            collection_color=collection.color if collection else None,
        )
        for run, test, version, collection in rows
    ]


@router.get("/runs", response_model=list[RunListResponse])
async def list_all_runs(
    status: str | None = None,
    test_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all test runs with filtering for current user."""
    query = (
        select(Run, Test, TestVersion, Collection)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .outerjoin(Collection, Test.collection_id == Collection.id)
        .where(tenant_filter(Test, current_user))
    )

    if status:
        query = query.where(Run.status == status)

    if test_id:
        query = query.where(Test.id == test_id)

    query = query.order_by(Run.started_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    # #region agent log
    try:
        import urllib.request
        import json

        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "F",
            "location": "dashboard.py:219",
            "message": "Dashboard runs query executed",
            "data": {
                "rows_count": len(rows),
                "status_filter": status,
                "test_id_filter": str(test_id) if test_id else None,
                "limit": limit,
                "offset": offset,
            },
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
        }
        req = urllib.request.Request(
            "http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80",
            data=json.dumps(log_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=0.5)
    except Exception:
        pass
    # #endregion

    runs = []
    for run, test, version, collection in rows:
        duration_ms = None
        if run.started_at and run.finished_at:
            duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)

        runs.append(RunListResponse(
            id=run.id,
            test_id=test.id,
            test_name=test.name,
            version_number=version.version_number,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error_message=run.error_message,
            duration_ms=duration_ms,
            collection_name=collection.name if collection else None,
            collection_color=collection.color if collection else None,
        ))

    return runs
