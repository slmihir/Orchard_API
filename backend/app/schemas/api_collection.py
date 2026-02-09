"""Pydantic schemas for API Collections."""

from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    """Authentication configuration for API collections."""
    type: Literal["bearer", "basic", "api_key", "oauth2", "none"] = "none"
    config: dict = Field(default_factory=dict)
    # For bearer: {"token": "..."}
    # For basic: {"username": "...", "password": "..."}
    # For api_key: {"key": "...", "value": "...", "in": "header|query"}
    # For oauth2: {"client_id": "...", "client_secret": "...", "token_url": "...", ...}


class VariableDefinition(BaseModel):
    """Variable definition with type information."""
    value: str | int | float | bool
    type: Literal["string", "number", "boolean"] = "string"
    description: str | None = None


class APICollectionCreate(BaseModel):
    """Schema for creating an API collection."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    base_url: str | None = None
    auth_config: AuthConfig | None = None
    variables: dict[str, VariableDefinition] | None = None
    default_headers: dict[str, str] | None = None
    default_engine: Literal["python", "karate"] = "python"


class APICollectionUpdate(BaseModel):
    """Schema for updating an API collection."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    base_url: str | None = None
    auth_config: AuthConfig | None = None
    variables: dict[str, VariableDefinition] | None = None
    default_headers: dict[str, str] | None = None
    default_engine: Literal["python", "karate"] | None = None


class APICollectionResponse(BaseModel):
    """Schema for API collection response."""
    id: UUID
    name: str
    description: str | None = None
    base_url: str | None = None
    auth_config: dict | None = None
    variables: dict | None = None
    default_headers: dict | None = None
    default_engine: str
    import_source: str | None = None
    import_source_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class APICollectionSummary(BaseModel):
    """Summary schema for listing API collections."""
    id: UUID
    name: str
    description: str | None = None
    base_url: str | None = None
    default_engine: str
    import_source: str | None = None
    request_count: int = 0
    environment_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class APICollectionDetailResponse(APICollectionResponse):
    """Detailed API collection response with related data."""
    requests: list["APIRequestResponse"] = []
    environments: list["APIEnvironmentResponse"] = []

    model_config = {"from_attributes": True}


# Import at end to avoid circular imports
from app.schemas.api_request import APIRequestResponse
from app.schemas.api_environment import APIEnvironmentResponse

APICollectionDetailResponse.model_rebuild()
