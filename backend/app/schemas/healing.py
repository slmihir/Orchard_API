"""Schemas for healing API."""

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class HealingSuggestionResponse(BaseModel):
    id: UUID
    run_id: UUID
    step_id: UUID
    step_index: int

    original_selector: str
    suggested_selector: str
    alternative_selectors: Optional[list[str]] = None

    confidence: float
    reasoning: Optional[str] = None
    selector_type: str

    status: str
    auto_approved: bool

    created_at: datetime
    applied_at: Optional[datetime] = None
    retry_success: Optional[bool] = None

    class Config:
        from_attributes = True


class HealingSuggestionApprove(BaseModel):
    """Request to approve a healing suggestion."""
    apply_to_test: bool = True  # If True, update the step in the test


class HealingSuggestionBulkAction(BaseModel):
    """Bulk approve/reject suggestions."""
    suggestion_ids: list[UUID]
    action: str  # "approve" or "reject"
    apply_to_test: bool = True


class HealingSettingsResponse(BaseModel):
    """Current healing settings."""
    enabled: bool
    auto_approve_threshold: float
    mode: str  # inline, batch, both
    default_provider: str


class HealingSettingsUpdate(BaseModel):
    """Update healing settings."""
    enabled: Optional[bool] = None
    auto_approve_threshold: Optional[float] = None
    mode: Optional[str] = None
