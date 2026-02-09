"""API Requests CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.db.postgres import get_db
from app.models.api_collection import APICollection
from app.models.api_request import APIRequest
from app.models.user import User
from app.schemas.api_request import (
    APIRequestCreate,
    APIRequestUpdate,
    APIRequestResponse,
    ReorderRequestsRequest,
)
from app.security import get_current_user
from app.utils.tenant import tenant_filter

router = APIRouter()


@router.get("", response_model=list[APIRequestResponse])
async def list_requests(
    collection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all requests in a collection."""
    # Verify collection access
    collection_result = await db.execute(
        select(APICollection)
        .where(
            APICollection.id == collection_id,
            tenant_filter(APICollection, current_user),
        )
    )
    if not collection_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Collection not found")

    result = await db.execute(
        select(APIRequest)
        .where(APIRequest.collection_id == collection_id)
        .order_by(APIRequest.order_index)
    )
    requests = result.scalars().all()

    return [APIRequestResponse.model_validate(r) for r in requests]


@router.post("", response_model=APIRequestResponse)
async def create_request(
    data: APIRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API request in a collection."""
    # Verify collection access
    collection_result = await db.execute(
        select(APICollection)
        .where(
            APICollection.id == data.collection_id,
            tenant_filter(APICollection, current_user),
        )
    )
    if not collection_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Collection not found")

    request = APIRequest(
        collection_id=data.collection_id,
        name=data.name,
        description=data.description,
        order_index=data.order_index,
        method=data.method,
        url_path=data.url_path,
        headers=data.headers,
        query_params=data.query_params,
        body=data.body.model_dump() if data.body else None,
        assertions=[a.model_dump() for a in data.assertions] if data.assertions else None,
        variable_extractions=[v.model_dump() for v in data.variable_extractions] if data.variable_extractions else None,
        pre_request_script=data.pre_request_script,
        pre_request_script_type=data.pre_request_script_type,
        post_response_script=data.post_response_script,
        post_response_script_type=data.post_response_script_type,
        engine=data.engine,
        folder_path=data.folder_path,
        timeout_ms=data.timeout_ms,
    )

    db.add(request)
    await db.commit()
    await db.refresh(request)

    return APIRequestResponse.model_validate(request)


@router.get("/{request_id}", response_model=APIRequestResponse)
async def get_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single API request."""
    result = await db.execute(
        select(APIRequest)
        .join(APICollection)
        .where(
            APIRequest.id == request_id,
            tenant_filter(APICollection, current_user),
        )
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    return APIRequestResponse.model_validate(request)


@router.patch("/{request_id}", response_model=APIRequestResponse)
async def update_request(
    request_id: UUID,
    data: APIRequestUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an API request."""
    result = await db.execute(
        select(APIRequest)
        .join(APICollection)
        .where(
            APIRequest.id == request_id,
            tenant_filter(APICollection, current_user),
        )
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Update fields
    if data.name is not None:
        request.name = data.name
    if data.description is not None:
        request.description = data.description
    if data.order_index is not None:
        request.order_index = data.order_index
    if data.method is not None:
        request.method = data.method
    if data.url_path is not None:
        request.url_path = data.url_path
    if data.headers is not None:
        request.headers = data.headers
    if data.query_params is not None:
        request.query_params = data.query_params
    if data.body is not None:
        request.body = data.body.model_dump()
    if data.assertions is not None:
        request.assertions = [a.model_dump() for a in data.assertions]
    if data.variable_extractions is not None:
        request.variable_extractions = [v.model_dump() for v in data.variable_extractions]
    if data.pre_request_script is not None:
        request.pre_request_script = data.pre_request_script
    if data.pre_request_script_type is not None:
        request.pre_request_script_type = data.pre_request_script_type
    if data.post_response_script is not None:
        request.post_response_script = data.post_response_script
    if data.post_response_script_type is not None:
        request.post_response_script_type = data.post_response_script_type
    if data.engine is not None:
        request.engine = data.engine
    if data.folder_path is not None:
        request.folder_path = data.folder_path
    if data.timeout_ms is not None:
        request.timeout_ms = data.timeout_ms

    await db.commit()
    await db.refresh(request)

    return APIRequestResponse.model_validate(request)


@router.delete("/{request_id}")
async def delete_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an API request."""
    result = await db.execute(
        select(APIRequest)
        .join(APICollection)
        .where(
            APIRequest.id == request_id,
            tenant_filter(APICollection, current_user),
        )
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    await db.delete(request)
    await db.commit()

    return {"status": "deleted"}


@router.post("/{request_id}/duplicate", response_model=APIRequestResponse)
async def duplicate_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Duplicate an API request."""
    result = await db.execute(
        select(APIRequest)
        .join(APICollection)
        .where(
            APIRequest.id == request_id,
            tenant_filter(APICollection, current_user),
        )
    )
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(status_code=404, detail="Request not found")

    # Create copy
    duplicate = APIRequest(
        collection_id=original.collection_id,
        name=f"{original.name} (Copy)",
        description=original.description,
        order_index=original.order_index + 1,
        method=original.method,
        url_path=original.url_path,
        headers=original.headers,
        query_params=original.query_params,
        body=original.body,
        assertions=original.assertions,
        variable_extractions=original.variable_extractions,
        pre_request_script=original.pre_request_script,
        pre_request_script_type=original.pre_request_script_type,
        post_response_script=original.post_response_script,
        post_response_script_type=original.post_response_script_type,
        engine=original.engine,
        folder_path=original.folder_path,
        timeout_ms=original.timeout_ms,
    )

    db.add(duplicate)
    await db.commit()
    await db.refresh(duplicate)

    return APIRequestResponse.model_validate(duplicate)


@router.post("/reorder")
async def reorder_requests(
    data: ReorderRequestsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reorder requests in a collection."""
    for idx, request_id in enumerate(data.request_ids):
        result = await db.execute(
            select(APIRequest)
            .join(APICollection)
            .where(
                APIRequest.id == request_id,
                tenant_filter(APICollection, current_user),
            )
        )
        request = result.scalar_one_or_none()

        if request:
            request.order_index = idx

    await db.commit()

    return {"status": "reordered", "count": len(data.request_ids)}
