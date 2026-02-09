from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Literal


# Action step types
ActionStepType = Literal["navigate", "click", "fill", "wait", "scroll", "hover"]

# Assertion step types
AssertionStepType = Literal[
    "assert_visible",      # Element exists and is visible
    "assert_hidden",       # Element is not visible
    "assert_text",         # Element contains expected text
    "assert_value",        # Input has expected value
    "assert_attribute",    # Element has attribute value
    "assert_url",          # Current URL matches pattern
    "assert_api",          # API response validation
    "assert_vision",       # Vision-based assertion using LLM
]

# Combined step types
StepType = Literal[
    "navigate", "click", "fill", "wait", "scroll", "hover",
    "assert_visible", "assert_hidden", "assert_text",
    "assert_value", "assert_attribute", "assert_url", "assert_api",
    "assert_vision"
]


class AssertionConfig(BaseModel):
    """Configuration for assertion steps."""
    expected: str | None = None                    # Expected text/value
    operator: str = "equals"                       # equals, contains, matches, gt, lt
    attribute: str | None = None                   # For assert_attribute (e.g., "disabled", "href")
    api_method: str | None = None                  # GET, POST, etc. for assert_api
    api_url_pattern: str | None = None             # URL pattern to match for assert_api
    api_status: int | None = None                  # Expected status code for assert_api
    api_body_contains: str | None = None           # Expected content in response body


class StepBase(BaseModel):
    type: StepType
    selector: str | None = None
    value: str | None = None
    screenshot_url: str | None = None
    assertion_config: AssertionConfig | None = None


class StepCreate(StepBase):
    order_index: int


class StepUpdate(BaseModel):
    type: StepType | None = None
    selector: str | None = None
    value: str | None = None
    order_index: int | None = None
    assertion_config: AssertionConfig | None = None


class StepResponse(StepBase):
    id: UUID
    order_index: int
    created_at: datetime
    assertion_config: AssertionConfig | None = None

    class Config:
        from_attributes = True


class StepReorder(BaseModel):
    step_ids: list[UUID]  # New order of step IDs
