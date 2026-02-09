"""Schemas for user settings API."""

from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class HealingSettingsResponse(BaseModel):
    """Healing settings for display."""
    enabled: bool
    auto_approve: bool
    auto_approve_threshold: float
    mode: str
    provider: str

    class Config:
        from_attributes = True


class HealingSettingsUpdate(BaseModel):
    """Update healing settings."""
    enabled: Optional[bool] = None
    auto_approve: Optional[bool] = None
    auto_approve_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    mode: Optional[str] = Field(None, pattern="^(inline|batch|both)$")
    provider: Optional[str] = Field(None, pattern="^(gemini|openai|anthropic)$")


class UserSettingsResponse(BaseModel):
    """Full user settings response."""
    id: UUID
    user_id: UUID
    healing_enabled: bool
    healing_auto_approve: bool
    healing_auto_approve_threshold: float
    healing_mode: str
    healing_provider: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LLMProviderOption(BaseModel):
    """LLM provider option for UI."""
    id: str
    name: str
    available: bool
    description: str
