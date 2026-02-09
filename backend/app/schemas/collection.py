from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CollectionBase(BaseModel):
    name: str
    description: str | None = None
    color: str | None = "#6366f1"


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class CollectionResponse(CollectionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    test_count: int = 0

    class Config:
        from_attributes = True
