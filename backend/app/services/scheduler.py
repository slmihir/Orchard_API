"""Background scheduler that runs scheduled tests."""

import asyncio
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.postgres import AsyncSessionLocal
from app.models.schedule import Schedule
from app.models.schedule_run import ScheduleRun
from app.models.test import Test, TestVersion, Step, Collection
from app.models.run import Run
from app.services.test_runner import PlaywrightTestRunner


def calculate_next_run(schedule: Schedule) -> datetime:
    """Calculate the next run time based on schedule settings."""
    now = datetime.utcnow()

    if schedule.frequency == 'hourly':
        next_run = now.replace(minute=schedule.run_at_minute or 0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(hours=1)
        return next_run

    elif schedule.frequency == 'daily':
        next_run = now.replace(
            hour=schedule.run_at_hour or 9,
            minute=schedule.run_at_minute or 0,
            second=0,
            microsecond=0
        )
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run

    elif schedule.frequency == 'weekly':
        run_days = [int(d) for d in (schedule.run_on_days or "1,2,3,4,5").split(",")]
        next_run = now.replace(
            hour=schedule.run_at_hour or 9,
            minute=schedule.run_at_minute or 0,
            second=0,
            microsecond=0
        )

        for i in range(8):
            check_date = next_run + timedelta(days=i)
            if check_date.weekday() in [d % 7 for d in run_days]:
                if check_date > now:
                    return check_date

        return next_run + timedelta(days=1)

    else:
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run


async def run_single_test(test: Test, schedule_run_id: UUID = None) -> tuple[bool, str, UUID]:
    """Run a single test and return success status, message, and run ID."""
    async with AsyncSessionLocal() as db:
        version_result = await db.execute(
            select(TestVersion)
            .where(TestVersion.test_id == test.id)
            .order_by(TestVersion.version_number.desc())
            .limit(1)
        )
        version = version_result.scalar_one_or_none()

        if not version:
            return False, f"No version found for test: {test.name}", None

        steps_result = await db.execute(
            select(Step)
            .where(Step.version_id == version.id)
            .order_by(Step.order_index)
        )
        steps = steps_result.scalars().all()

        if not steps:
            return False, f"No steps found for test: {test.name}", None

        run = Run(
            version_id=version.id,
            schedule_run_id=schedule_run_id,
            status="running"
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

    # Prepare steps data
    steps_data = [
        {
            "type": step.type,
            "selector": step.selector,
            "value": step.value,
        }
        for step in steps
    ]

    runner = PlaywrightTestRunner()
    result = await runner.run(steps_data, test.target_url)

    async with AsyncSessionLocal() as db:
        run_result = await db.execute(select(Run).where(Run.id == run_id))
        run = run_result.scalar_one()
        run.status = "passed" if result["success"] else "failed"
        run.finished_at = datetime.utcnow()
        if not result["success"]:
            run.error_message = result["message"]
        await db.commit()

    return result["success"], result.get("message", ""), run_id


async def run_scheduled_test(schedule: Schedule) -> tuple[bool, str]:
    """Run a scheduled single test."""
    print(f"[Scheduler] Running scheduled test: {schedule.name}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Test).where(Test.id == schedule.test_id)
        )
        test = result.scalar_one_or_none()

        if not test:
            print(f"[Scheduler] Test not found for schedule: {schedule.name}")
            return False, "Test not found"

        schedule_run = ScheduleRun(
            schedule_id=schedule.id,
            status="running",
            total_tests=1,
        )
        db.add(schedule_run)
        await db.commit()
        await db.refresh(schedule_run)
        schedule_run_id = schedule_run.id

    success, message, run_id = await run_single_test(test, schedule_run_id)

    async with AsyncSessionLocal() as db:
        sr_result = await db.execute(select(ScheduleRun).where(ScheduleRun.id == schedule_run_id))
        schedule_run = sr_result.scalar_one()
        schedule_run.status = "passed" if success else "failed"
        schedule_run.finished_at = datetime.utcnow()
        schedule_run.passed_tests = 1 if success else 0
        schedule_run.failed_tests = 0 if success else 1
        if not success:
            schedule_run.error_message = message[:1000] if message else None
        await db.commit()

    print(f"[Scheduler] Test '{test.name}' completed with status: {'passed' if success else 'failed'}")
    return success, message


async def run_scheduled_collection(schedule: Schedule) -> tuple[bool, str]:
    """Run all tests in a scheduled collection."""
    print(f"[Scheduler] Running scheduled collection: {schedule.name}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Collection).where(Collection.id == schedule.collection_id)
        )
        collection = result.scalar_one_or_none()

        if not collection:
            print(f"[Scheduler] Collection not found for schedule: {schedule.name}")
            return False, "Collection not found"

        tests_result = await db.execute(
            select(Test).where(Test.collection_id == schedule.collection_id)
        )
        tests = tests_result.scalars().all()

        if not tests:
            print(f"[Scheduler] No tests found in collection: {collection.name}")
            return False, f"No tests in collection: {collection.name}"

        schedule_run = ScheduleRun(
            schedule_id=schedule.id,
            status="running",
            total_tests=len(tests),
        )
        db.add(schedule_run)
        await db.commit()
        await db.refresh(schedule_run)
        schedule_run_id = schedule_run.id

    total_tests = len(tests)
    passed_tests = 0
    failed_tests = 0
    failed_messages = []

    print(f"[Scheduler] Running {total_tests} tests in collection '{collection.name}'")

    for test in tests:
        success, message, run_id = await run_single_test(test, schedule_run_id)
        if success:
            passed_tests += 1
        else:
            failed_tests += 1
            failed_messages.append(f"{test.name}: {message}")

    # Determine overall status
    all_passed = failed_tests == 0
    summary = f"{passed_tests}/{total_tests} tests passed"
    if failed_messages:
        summary += f". Failed: {'; '.join(failed_messages[:3])}"
        if len(failed_messages) > 3:
            summary += f" (+{len(failed_messages) - 3} more)"

    async with AsyncSessionLocal() as db:
        sr_result = await db.execute(select(ScheduleRun).where(ScheduleRun.id == schedule_run_id))
        schedule_run = sr_result.scalar_one()
        schedule_run.status = "passed" if all_passed else "failed"
        schedule_run.finished_at = datetime.utcnow()
        schedule_run.passed_tests = passed_tests
        schedule_run.failed_tests = failed_tests
        if not all_passed:
            schedule_run.error_message = summary[:1000]
        await db.commit()

    print(f"[Scheduler] Collection '{collection.name}' completed: {summary}")
    return all_passed, summary


async def check_and_run_schedules():
    """Check for due schedules and run them."""
    now = datetime.utcnow()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Schedule)
            .where(Schedule.enabled == True)
            .where(Schedule.next_run_at <= now)
        )
        due_schedules = result.scalars().all()

        for schedule in due_schedules:
            print(f"[Scheduler] Schedule '{schedule.name}' is due to run")

            try:
                if schedule.collection_id:
                    success, message = await run_scheduled_collection(schedule)
                else:
                    success, message = await run_scheduled_test(schedule)

                schedule.last_run_at = datetime.utcnow()
                schedule.last_run_status = "passed" if success else "failed"
                schedule.next_run_at = calculate_next_run(schedule)
                await db.commit()

                print(f"[Scheduler] Updated schedule '{schedule.name}', next run at: {schedule.next_run_at}")

            except Exception as e:
                print(f"[Scheduler] Error running schedule '{schedule.name}': {e}")
                schedule.last_run_at = datetime.utcnow()
                schedule.last_run_status = "failed"
                schedule.next_run_at = calculate_next_run(schedule)
                await db.commit()


class BackgroundScheduler:
    """Background scheduler that periodically checks and runs due schedules."""

    def __init__(self, check_interval: int = 60):
        """
        Initialize the scheduler.

        Args:
            check_interval: How often to check for due schedules (in seconds)
        """
        self.check_interval = check_interval
        self.running = False
        self.task = None

    async def _run_loop(self):
        """Main scheduler loop."""
        print(f"[Scheduler] Starting scheduler loop (check interval: {self.check_interval}s)")

        while self.running:
            try:
                await check_and_run_schedules()
            except Exception as e:
                print(f"[Scheduler] Error in scheduler loop: {e}")

            await asyncio.sleep(self.check_interval)

    async def start(self):
        """Start the background scheduler."""
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        print("[Scheduler] Background scheduler started")

    async def stop(self):
        """Stop the background scheduler."""
        if not self.running:
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        print("[Scheduler] Background scheduler stopped")


# Global scheduler instance
scheduler = BackgroundScheduler()
