from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
import json
import asyncio

from app.db.postgres import get_db, AsyncSessionLocal
from app.models.test import Test, TestVersion, Step
from app.models.run import Run
from app.models.healing import HealingSuggestion
from app.models.settings import UserSettings
from app.models.user import User
from app.services.test_runner import PlaywrightTestRunner
from app.config import get_settings
from app.security import get_current_user
from app.utils.tenant import tenant_filter
from jose import jwt, JWTError

config = get_settings()

router = APIRouter()


class RunResponse(BaseModel):
    id: UUID
    version_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None

    class Config:
        from_attributes = True


class RunCreate(BaseModel):
    version_id: UUID


@router.post("", response_model=RunResponse)
async def start_run(
    run_data: RunCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a run record. Use WebSocket endpoint to actually run the test."""
    result = await db.execute(
        select(TestVersion)
        .join(Test, TestVersion.test_id == Test.id)
        .where(TestVersion.id == run_data.version_id, tenant_filter(Test, current_user))
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Test version not found")

    run = Run(
        version_id=run_data.version_id,
        status="pending"
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    return run


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Run)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(Run.id == run_id, tenant_filter(Test, current_user))
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return run


@router.get("/version/{version_id}", response_model=list[RunResponse])
async def list_runs_for_version(
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    version_result = await db.execute(
        select(TestVersion)
        .join(Test, TestVersion.test_id == Test.id)
        .where(TestVersion.id == version_id, tenant_filter(Test, current_user))
    )
    if not version_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test version not found")

    result = await db.execute(
        select(Run)
        .where(Run.version_id == version_id)
        .order_by(Run.started_at.desc())
    )
    return result.scalars().all()


async def get_user_from_token(token: str, db) -> User | None:
    """Get user from JWT token."""
    try:
        payload = jwt.decode(token, config.secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            return None

        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except JWTError:
        return None


async def get_user_healing_config(user_id: UUID, db) -> dict:
    """Get user's healing settings."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if settings:
        return {
            "enabled": settings.healing_enabled,
            "auto_approve": settings.healing_auto_approve,
            "auto_approve_threshold": settings.healing_auto_approve_threshold,
            "mode": settings.healing_mode,
            "provider": settings.healing_provider,
        }
    return None


@router.websocket("/ws/{test_id}")
async def run_test_websocket(websocket: WebSocket, test_id: str, token: str = None):
    """Run a saved test with real-time screenshot streaming."""
    await websocket.accept()

    # Event for approval flow
    approval_event = asyncio.Event()
    approval_response = {"approved": False}

    try:
        async with AsyncSessionLocal() as db:
            current_user = None
            if token:
                current_user = await get_user_from_token(token, db)

            if not current_user:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Unauthorized"}
                })
                return

            result = await db.execute(
                select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
            )
            test = result.scalar_one_or_none()

            if not test:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Test not found"}
                })
                return

            version_result = await db.execute(
                select(TestVersion)
                .where(TestVersion.test_id == test_id)
                .order_by(TestVersion.version_number.desc())
                .limit(1)
            )
            version = version_result.scalar_one_or_none()

            if not version:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "No test version found"}
                })
                return

            steps_result = await db.execute(
                select(Step)
                .where(Step.version_id == version.id)
                .order_by(Step.order_index)
            )
            steps = steps_result.scalars().all()

            run = Run(version_id=version.id, status="running")
            db.add(run)
            await db.commit()
            await db.refresh(run)
            run_id = run.id

            healer_config = await get_user_healing_config(current_user.id, db)

        # Prepare steps data (include step_id and assertion_config)
        steps_data = [
            {
                "step_id": str(step.id),
                "type": step.type,
                "selector": step.selector,
                "value": step.value,
                "assertion_config": step.assertion_config,
            }
            for step in steps
        ]

        # Keep step IDs for healing suggestions
        step_ids = [step.id for step in steps]

        async def on_step(step_data: dict):
            await websocket.send_json({
                "type": "step",
                "data": step_data
            })

        async def on_screenshot(screenshot: str):
            await websocket.send_json({
                "type": "screenshot",
                "data": {"image": screenshot}
            })

        async def on_metrics(metrics: dict):
            await websocket.send_json({
                "type": "metrics",
                "data": metrics
            })

        async def on_dialog(dialog_info: dict):
            await websocket.send_json({
                "type": "dialog",
                "data": dialog_info
            })

        async def on_healing(healing_data: dict):
            await websocket.send_json({
                "type": "healing",
                "data": healing_data
            })

        async def on_approval_request(healing_data: dict) -> dict:
            """Request approval from user and wait for response."""
            nonlocal approval_response
            approval_event.clear()
            approval_response = {"approved": False}

            await websocket.send_json({
                "type": "approval_request",
                "data": healing_data
            })

            # Wait for approval response (timeout after 60 seconds)
            try:
                await asyncio.wait_for(approval_event.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                return {"approved": False, "reason": "timeout"}

            return approval_response

        use_approval = healer_config and not healer_config.get('auto_approve', False)

        runner = PlaywrightTestRunner(
            on_step=on_step,
            on_screenshot=on_screenshot,
            on_metrics=on_metrics,
            on_dialog=on_dialog,
            on_healing=on_healing,
            on_approval_request=on_approval_request if use_approval else None,
            healer_config=healer_config,
        )

        await websocket.send_json({
            "type": "status",
            "data": {"status": "starting", "run_id": str(run_id)}
        })

        await websocket.send_json({
            "type": "status",
            "data": {"status": "running"}
        })

        # Run test in a task so we can also listen for messages
        async def run_test():
            return await runner.run(steps_data, test.target_url)

        test_task = asyncio.create_task(run_test())

        # Listen for incoming messages while test runs
        async def listen_for_messages():
            try:
                while not test_task.done():
                    try:
                        message = await asyncio.wait_for(websocket.receive_json(), timeout=0.5)
                        if message.get("type") == "approval_response":
                            nonlocal approval_response
                            approval_response = message.get("data", {})
                            approval_event.set()
                    except asyncio.TimeoutError:
                        continue
                    except WebSocketDisconnect:
                        break
            except Exception as e:
                print(f"[WebSocket] Message listener error: {e}")

        # Run both concurrently
        listener_task = asyncio.create_task(listen_for_messages())

        try:
            result = await test_task
        finally:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        async with AsyncSessionLocal() as db:
            run_result = await db.execute(select(Run).where(Run.id == run_id))
            run = run_result.scalar_one()
            run.status = "passed" if result["success"] else "failed"
            run.finished_at = datetime.utcnow()
            if not result["success"]:
                run.error_message = result["message"]

            healing_suggestions = result.get("healing_suggestions", [])
            for suggestion in healing_suggestions:
                step_index = suggestion.get("step_index", 0)
                step_id = step_ids[step_index] if step_index < len(step_ids) else None

                if step_id:
                    # Determine status based on what happened
                    if suggestion.get("auto_approved"):
                        status = "auto_applied"
                    elif suggestion.get("user_approved"):
                        status = "approved"
                    else:
                        status = "pending"

                    db_suggestion = HealingSuggestion(
                        run_id=run_id,
                        step_id=step_id,
                        step_index=step_index,
                        original_selector=suggestion.get("original_selector", ""),
                        suggested_selector=suggestion.get("suggested_selector", ""),
                        alternative_selectors=suggestion.get("alternative_selectors"),
                        confidence=suggestion.get("confidence", 0.0),
                        reasoning=suggestion.get("reasoning"),
                        selector_type="css",
                        status=status,
                        auto_approved=suggestion.get("auto_approved", False),
                        context_snapshot=suggestion.get("context"),
                        retry_success=suggestion.get("retry_success", False),
                    )
                    db.add(db_suggestion)

                    # If user approved and retry succeeded, update the step
                    if suggestion.get("user_approved") and suggestion.get("retry_success"):
                        await db.execute(
                            update(Step)
                            .where(Step.id == step_id)
                            .values(selector=suggestion.get("suggested_selector"))
                        )

            await db.commit()

        await websocket.send_json({
            "type": "complete",
            "data": result
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass
