"""Pydantic schemas for API test assertions and variable extraction."""

from typing import Literal, Any
from pydantic import BaseModel, Field


class StatusAssertionConfig(BaseModel):
    """Configuration for status code assertion."""
    expected: int | list[int]  # Single value or list for 'in' operator
    operator: Literal["equals", "in", "range"] = "equals"
    # For range: expected should be [min, max]


class JSONPathAssertionConfig(BaseModel):
    """Configuration for JSONPath assertion."""
    path: str = Field(..., description="JSONPath expression, e.g., $.data.id")
    expected: Any = None  # Expected value to compare
    operator: Literal["equals", "not_equals", "contains", "not_contains", "exists", "not_exists", "greater_than", "less_than", "matches"] = "equals"


class HeaderAssertionConfig(BaseModel):
    """Configuration for header assertion."""
    name: str = Field(..., description="Header name (case-insensitive)")
    expected: str | None = None  # Expected value, None for existence check
    operator: Literal["equals", "contains", "exists", "not_exists", "matches"] = "exists"


class TimingAssertionConfig(BaseModel):
    """Configuration for response time assertion."""
    max_ms: int = Field(..., ge=1, description="Maximum response time in milliseconds")


class SchemaAssertionConfig(BaseModel):
    """Configuration for JSON Schema validation."""
    schema_def: dict = Field(..., alias="schema", description="JSON Schema definition")


class BodyContainsAssertionConfig(BaseModel):
    """Configuration for body substring assertion."""
    expected: str = Field(..., description="Substring to find in response body")
    case_sensitive: bool = True


class AssertionConfig(BaseModel):
    """Generic assertion configuration."""
    type: Literal["status", "jsonpath", "header", "timing", "schema", "body_contains", "body_equals"]
    name: str | None = Field(None, description="Optional name for the assertion")
    config: dict = Field(default_factory=dict)
    # Config structure depends on type:
    # - status: StatusAssertionConfig
    # - jsonpath: JSONPathAssertionConfig
    # - header: HeaderAssertionConfig
    # - timing: TimingAssertionConfig
    # - schema: SchemaAssertionConfig
    # - body_contains: BodyContainsAssertionConfig
    # - body_equals: {"expected": "..."}


class AssertionResult(BaseModel):
    """Result of a single assertion execution."""
    type: str
    name: str | None = None
    passed: bool
    expected: Any = None
    actual: Any = None
    message: str | None = None


class VariableExtraction(BaseModel):
    """Configuration for extracting variables from response."""
    name: str = Field(..., min_length=1, max_length=100, description="Variable name to store extracted value")
    source: Literal["jsonpath", "header", "body", "status", "regex"] = "jsonpath"
    path: str = Field(..., description="Extraction path (JSONPath, header name, or regex pattern)")
    default: Any = None  # Default value if extraction fails


class ExtractedVariable(BaseModel):
    """Result of variable extraction."""
    name: str
    value: Any
    source: str
    path: str
