"""Pydantic schemas for API Environments."""

from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, Field


class EnvironmentVariable(BaseModel):
    """Environment variable with type and secret flag."""
    value: str | int | float | bool
    type: Literal["string", "number", "boolean"] = "string"
    secret: bool = False  # If true, value should be masked in UI
    description: str | None = None


class APIEnvironmentCreate(BaseModel):
    """Schema for creating an API environment."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    collection_id: UUID | None = None  # If None, environment is global to tenant
    variables: dict[str, EnvironmentVariable] | None = None
    base_url: str | None = None  # Override collection base_url
    auth_config: dict | None = None  # Override collection auth_config
    default_headers: dict[str, str] | None = None  # Override collection headers
    is_default: bool = False


class APIEnvironmentUpdate(BaseModel):
    """Schema for updating an API environment."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    variables: dict[str, EnvironmentVariable] | None = None
    base_url: str | None = None
    auth_config: dict | None = None
    default_headers: dict[str, str] | None = None
    is_default: bool | None = None


class APIEnvironmentResponse(BaseModel):
    """Schema for API environment response."""
    id: UUID
    name: str
    description: str | None = None
    collection_id: UUID | None = None
    variables: dict | None = None
    base_url: str | None = None
    auth_config: dict | None = None
    default_headers: dict | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class APIEnvironmentSummary(BaseModel):
    """Summary schema for listing environments."""
    id: UUID
    name: str
    description: str | None = None
    collection_id: UUID | None = None
    is_default: bool
    variable_count: int = 0

    model_config = {"from_attributes": True}
