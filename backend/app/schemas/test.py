from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.schemas.step import StepResponse, StepCreate


class TestBase(BaseModel):
    name: str
    description: str | None = None
    target_url: str
    collection_id: UUID | None = None


class TestCreate(TestBase):
    steps: list[StepCreate] = []


class TestUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_url: str | None = None
    collection_id: UUID | None = None


class TestVersionResponse(BaseModel):
    id: UUID
    version_number: int
    created_at: datetime
    steps: list[StepResponse] = []

    class Config:
        from_attributes = True


class CollectionBasic(BaseModel):
    id: UUID
    name: str
    color: str | None

    class Config:
        from_attributes = True


class TestResponse(TestBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    latest_version: TestVersionResponse | None = None
    collection: CollectionBasic | None = None

    class Config:
        from_attributes = True


class TestListResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    target_url: str
    collection_id: UUID | None = None
    collection: CollectionBasic | None = None
    created_at: datetime
    version_count: int
    last_run_status: str | None = None

    class Config:
        from_attributes = True


class VariantChangeResponse(BaseModel):
    step_index: int
    new_value: str
    reason: str | None = None


class VariantResponse(BaseModel):
    name: str
    type: str
    description: str | None = None
    steps: list[dict]
    expected_result: str | None = None
    discovered_error: str | None = None
    has_assertion: bool = False


class GenerateVariantsRequest(BaseModel):
    variant_types: list[str] | None = None


class GenerateVariantsResponse(BaseModel):
    test_id: UUID
    test_name: str
    variants: list[VariantResponse]
