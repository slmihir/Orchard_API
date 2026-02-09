"""API endpoints for self-healing feature."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID
from datetime import datetime

from app.db.postgres import get_db
from app.models.healing import HealingSuggestion
from app.models.test import Test, TestVersion, Step
from app.models.run import Run
from app.models.user import User
from app.schemas.healing import (
    HealingSuggestionResponse,
    HealingSuggestionApprove,
    HealingSuggestionBulkAction,
    HealingSettingsResponse,
    HealingSettingsUpdate,
)
from app.config import get_settings
from app.security import get_current_user
from app.utils.tenant import tenant_filter

router = APIRouter()
settings = get_settings()


@router.get("", response_model=list[HealingSuggestionResponse])
async def list_suggestions(
    status: str = None,
    run_id: UUID = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List healing suggestions for current user's tests."""
    query = (
        select(HealingSuggestion)
        .join(Run, HealingSuggestion.run_id == Run.id)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(tenant_filter(Test, current_user))
        .order_by(HealingSuggestion.created_at.desc())
    )

    if status:
        query = query.where(HealingSuggestion.status == status)
    if run_id:
        query = query.where(HealingSuggestion.run_id == run_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/pending", response_model=list[HealingSuggestionResponse])
async def list_pending_suggestions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all pending suggestions awaiting approval for current user."""
    result = await db.execute(
        select(HealingSuggestion)
        .join(Run, HealingSuggestion.run_id == Run.id)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(tenant_filter(Test, current_user), HealingSuggestion.status == "pending")
        .order_by(HealingSuggestion.created_at.desc())
    )
    return result.scalars().all()


@router.get("/run/{run_id}", response_model=list[HealingSuggestionResponse])
async def get_suggestions_for_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all healing suggestions for a specific run (user's test only)."""
    run_check = await db.execute(
        select(Run)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(Run.id == run_id, tenant_filter(Test, current_user))
    )
    if not run_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Run not found")

    result = await db.execute(
        select(HealingSuggestion)
        .where(HealingSuggestion.run_id == run_id)
        .order_by(HealingSuggestion.step_index)
    )
    return result.scalars().all()


@router.get("/{suggestion_id}", response_model=HealingSuggestionResponse)
async def get_suggestion(
    suggestion_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific healing suggestion (user's test only)."""
    result = await db.execute(
        select(HealingSuggestion)
        .join(Run, HealingSuggestion.run_id == Run.id)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(HealingSuggestion.id == suggestion_id, tenant_filter(Test, current_user))
    )
    suggestion = result.scalar_one_or_none()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    return suggestion


@router.post("/{suggestion_id}/approve", response_model=HealingSuggestionResponse)
async def approve_suggestion(
    suggestion_id: UUID,
    data: HealingSuggestionApprove,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a healing suggestion and optionally apply to the test."""
    result = await db.execute(
        select(HealingSuggestion)
        .join(Run, HealingSuggestion.run_id == Run.id)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(HealingSuggestion.id == suggestion_id, tenant_filter(Test, current_user))
    )
    suggestion = result.scalar_one_or_none()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"Suggestion already {suggestion.status}")

    suggestion.status = "approved"
    suggestion.applied_at = datetime.utcnow()

    # Apply to test step if requested
    if data.apply_to_test:
        await db.execute(
            update(Step)
            .where(Step.id == suggestion.step_id)
            .values(selector=suggestion.suggested_selector)
        )

    await db.commit()
    await db.refresh(suggestion)

    return suggestion


@router.post("/{suggestion_id}/reject", response_model=HealingSuggestionResponse)
async def reject_suggestion(
    suggestion_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a healing suggestion."""
    result = await db.execute(
        select(HealingSuggestion)
        .join(Run, HealingSuggestion.run_id == Run.id)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(HealingSuggestion.id == suggestion_id, tenant_filter(Test, current_user))
    )
    suggestion = result.scalar_one_or_none()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"Suggestion already {suggestion.status}")

    suggestion.status = "rejected"
    await db.commit()
    await db.refresh(suggestion)

    return suggestion


@router.post("/bulk", response_model=list[HealingSuggestionResponse])
async def bulk_action(
    data: HealingSuggestionBulkAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk approve or reject suggestions (user's tests only)."""
    result = await db.execute(
        select(HealingSuggestion)
        .join(Run, HealingSuggestion.run_id == Run.id)
        .join(TestVersion, Run.version_id == TestVersion.id)
        .join(Test, TestVersion.test_id == Test.id)
        .where(
            HealingSuggestion.id.in_(data.suggestion_ids),
            HealingSuggestion.status == "pending",
            tenant_filter(Test, current_user)
        )
    )
    suggestions = result.scalars().all()

    if not suggestions:
        raise HTTPException(status_code=404, detail="No pending suggestions found")

    for suggestion in suggestions:
        if data.action == "approve":
            suggestion.status = "approved"
            suggestion.applied_at = datetime.utcnow()

            if data.apply_to_test:
                await db.execute(
                    update(Step)
                    .where(Step.id == suggestion.step_id)
                    .values(selector=suggestion.suggested_selector)
                )
        elif data.action == "reject":
            suggestion.status = "rejected"

    await db.commit()

    # Refresh all
    for suggestion in suggestions:
        await db.refresh(suggestion)

    return suggestions


@router.get("/settings", response_model=HealingSettingsResponse)
async def get_healing_settings():
    """Get current healing settings."""
    return HealingSettingsResponse(
        enabled=settings.healing_enabled,
        auto_approve_threshold=settings.healing_auto_approve_threshold,
        mode=settings.healing_mode,
        default_provider=settings.default_llm_provider,
    )
