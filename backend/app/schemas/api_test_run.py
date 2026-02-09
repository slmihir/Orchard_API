"""Pydantic schemas for API Test Runs and Results."""

from datetime import datetime
from uuid import UUID
from typing import Literal, Any
from pydantic import BaseModel, Field

from app.schemas.api_assertions import AssertionResult


class ExecuteCollectionRequest(BaseModel):
    """Schema for executing an API collection."""
    environment_id: UUID | None = None
    request_ids: list[UUID] | None = None  # Subset of requests to run (None = all)
    engine: Literal["python", "karate"] | None = None  # Override collection default
    stop_on_failure: bool = False  # Stop execution after first failure
    variables: dict[str, Any] | None = None  # Runtime variable overrides


class ExecuteSingleRequestRequest(BaseModel):
    """Schema for executing a single API request."""
    environment_id: UUID | None = None
    engine: Literal["python", "karate"] | None = None
    variables: dict[str, Any] | None = None  # Runtime variable overrides


class TimingBreakdown(BaseModel):
    """Detailed timing breakdown for HTTP request."""
    dns_ms: int | None = None
    connect_ms: int | None = None
    tls_ms: int | None = None
    ttfb_ms: int | None = None  # Time to first byte
    download_ms: int | None = None


class APIRequestResultResponse(BaseModel):
    """Schema for API request result response."""
    id: UUID
    test_run_id: UUID
    request_id: UUID
    execution_order: int
    status: str  # passed, failed, skipped, error

    # Request details (resolved)
    resolved_url: str | None = None
    resolved_method: str | None = None
    resolved_headers: dict | None = None
    resolved_body: str | None = None

    # Response details
    response_status: int | None = None
    response_headers: dict | None = None
    response_body: str | None = None
    response_size_bytes: int | None = None

    # Timing
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    timing_breakdown: TimingBreakdown | None = None

    # Assertions
    assertion_results: list[AssertionResult] | None = None

    # Extracted variables
    extracted_variables: dict | None = None

    # Errors
    error_message: str | None = None
    error_type: str | None = None

    # Script execution
    pre_script_executed: bool | None = None
    pre_script_error: str | None = None
    post_script_executed: bool | None = None
    post_script_error: str | None = None

    created_at: datetime

    model_config = {"from_attributes": True}


class APITestRunResponse(BaseModel):
    """Schema for API test run response."""
    id: UUID
    collection_id: UUID | None = None
    name: str | None = None
    trigger_type: str
    trigger_source: str | None = None
    environment_id: UUID | None = None
    engine: str
    status: str

    # Timing
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_duration_ms: int | None = None

    # Summary stats
    total_requests: int
    passed_requests: int
    failed_requests: int
    skipped_requests: int
    total_assertions: int
    passed_assertions: int
    failed_assertions: int

    # Errors
    error_message: str | None = None
    error_type: str | None = None

    # Karate-specific
    karate_job_id: str | None = None

    created_at: datetime

    model_config = {"from_attributes": True}


class APITestRunSummary(BaseModel):
    """Summary schema for listing test runs."""
    id: UUID
    collection_id: UUID | None = None
    collection_name: str | None = None
    name: str | None = None
    trigger_type: str
    engine: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_duration_ms: int | None = None
    total_requests: int
    passed_requests: int
    failed_requests: int
    created_at: datetime

    model_config = {"from_attributes": True}


class APITestRunDetailResponse(APITestRunResponse):
    """Detailed test run response with results."""
    results: list[APIRequestResultResponse] = []
    run_context: dict | None = None

    model_config = {"from_attributes": True}


# WebSocket message schemas
class WSExecutionMessage(BaseModel):
    """Base schema for WebSocket execution messages."""
    type: Literal["start", "request_start", "request_complete", "assertion", "variable", "status", "complete", "error"]
    data: dict = Field(default_factory=dict)


class WSStartCommand(BaseModel):
    """WebSocket command to start execution."""
    type: Literal["start"] = "start"
    environment_id: UUID | None = None
    request_ids: list[UUID] | None = None
    engine: Literal["python", "karate"] | None = None
    variables: dict | None = None
