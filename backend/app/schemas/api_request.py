"""Pydantic schemas for API Requests."""

from datetime import datetime
from uuid import UUID
from typing import Literal, Any
from pydantic import BaseModel, Field

from app.schemas.api_assertions import AssertionConfig, VariableExtraction


class RequestBody(BaseModel):
    """Request body configuration."""
    type: Literal["json", "form", "raw", "graphql", "none"] = "none"
    content: Any = None
    # For json: dict or list
    # For form: dict of key-value pairs
    # For raw: string content
    # For graphql: {"query": "...", "variables": {...}}


class APIRequestCreate(BaseModel):
    """Schema for creating an API request."""
    collection_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    order_index: int = 0
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = "GET"
    url_path: str = Field(..., min_length=1, max_length=1000)
    headers: dict[str, str] | None = None
    query_params: dict[str, str] | None = None
    body: RequestBody | None = None
    assertions: list[AssertionConfig] | None = None
    variable_extractions: list[VariableExtraction] | None = None
    pre_request_script: str | None = None
    pre_request_script_type: Literal["python", "karate"] | None = None
    post_response_script: str | None = None
    post_response_script_type: Literal["python", "karate"] | None = None
    engine: Literal["python", "karate"] | None = None
    folder_path: str | None = None
    timeout_ms: int | None = Field(None, ge=100, le=300000)


class APIRequestUpdate(BaseModel):
    """Schema for updating an API request."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    order_index: int | None = None
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] | None = None
    url_path: str | None = Field(None, min_length=1, max_length=1000)
    headers: dict[str, str] | None = None
    query_params: dict[str, str] | None = None
    body: RequestBody | None = None
    assertions: list[AssertionConfig] | None = None
    variable_extractions: list[VariableExtraction] | None = None
    pre_request_script: str | None = None
    pre_request_script_type: Literal["python", "karate"] | None = None
    post_response_script: str | None = None
    post_response_script_type: Literal["python", "karate"] | None = None
    engine: Literal["python", "karate"] | None = None
    folder_path: str | None = None
    timeout_ms: int | None = Field(None, ge=100, le=300000)


class APIRequestResponse(BaseModel):
    """Schema for API request response."""
    id: UUID
    collection_id: UUID
    name: str
    description: str | None = None
    order_index: int
    method: str
    url_path: str
    headers: dict | None = None
    query_params: dict | None = None
    body: dict | None = None
    assertions: list | None = None
    variable_extractions: list | None = None
    pre_request_script: str | None = None
    pre_request_script_type: str | None = None
    post_response_script: str | None = None
    post_response_script_type: str | None = None
    engine: str | None = None
    folder_path: str | None = None
    timeout_ms: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReorderRequestsRequest(BaseModel):
    """Schema for reordering requests in a collection."""
    request_ids: list[UUID] = Field(..., min_length=1)
