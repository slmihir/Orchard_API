"""API endpoints for user settings."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.postgres import get_db
from app.models.settings import UserSettings
from app.models.user import User
from app.schemas.settings import (
    HealingSettingsResponse,
    HealingSettingsUpdate,
    UserSettingsResponse,
    LLMProviderOption,
)
from app.security import get_current_user
from app.config import get_settings

router = APIRouter()
config = get_settings()


async def get_or_create_settings(user_id, db: AsyncSession) -> UserSettings:
    """Get user settings or create with defaults."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


@router.get("", response_model=UserSettingsResponse)
async def get_settings_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user settings."""
    settings = await get_or_create_settings(current_user.id, db)
    return settings


@router.get("/healing", response_model=HealingSettingsResponse)
async def get_healing_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get healing-specific settings."""
    settings = await get_or_create_settings(current_user.id, db)
    return HealingSettingsResponse(
        enabled=settings.healing_enabled,
        auto_approve=settings.healing_auto_approve,
        auto_approve_threshold=settings.healing_auto_approve_threshold,
        mode=settings.healing_mode,
        provider=settings.healing_provider,
    )


@router.patch("/healing", response_model=HealingSettingsResponse)
async def update_healing_settings(
    data: HealingSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update healing settings."""
    settings = await get_or_create_settings(current_user.id, db)

    if data.enabled is not None:
        settings.healing_enabled = data.enabled
    if data.auto_approve is not None:
        settings.healing_auto_approve = data.auto_approve
    if data.auto_approve_threshold is not None:
        settings.healing_auto_approve_threshold = data.auto_approve_threshold
    if data.mode is not None:
        settings.healing_mode = data.mode
    if data.provider is not None:
        settings.healing_provider = data.provider

    await db.commit()
    await db.refresh(settings)

    return HealingSettingsResponse(
        enabled=settings.healing_enabled,
        auto_approve=settings.healing_auto_approve,
        auto_approve_threshold=settings.healing_auto_approve_threshold,
        mode=settings.healing_mode,
        provider=settings.healing_provider,
    )


@router.get("/healing/providers", response_model=list[LLMProviderOption])
async def get_llm_providers():
    """Get available LLM providers."""
    providers = [
        LLMProviderOption(
            id="gemini",
            name="Google Gemini",
            available=bool(config.google_api_key),
            description="Google's Gemini 2.5 Flash model with vision capabilities",
        ),
        LLMProviderOption(
            id="openai",
            name="OpenAI GPT-4",
            available=bool(config.openai_api_key),
            description="OpenAI's GPT-4o model with vision capabilities",
        ),
        LLMProviderOption(
            id="anthropic",
            name="Anthropic Claude",
            available=bool(config.anthropic_api_key),
            description="Anthropic's Claude Sonnet model with vision capabilities",
        ),
    ]
    return providers
