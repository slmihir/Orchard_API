"""API Environments CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.db.postgres import get_db
from app.models.api_collection import APICollection
from app.models.api_environment import APIEnvironment
from app.models.user import User
from app.schemas.api_environment import (
    APIEnvironmentCreate,
    APIEnvironmentUpdate,
    APIEnvironmentResponse,
    APIEnvironmentSummary,
)
from app.security import get_current_user
from app.utils.tenant import tenant_filter, set_tenant

router = APIRouter()


@router.get("", response_model=list[APIEnvironmentSummary])
async def list_environments(
    collection_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List environments, optionally filtered by collection."""
    query = (
        select(APIEnvironment)
        .where(tenant_filter(APIEnvironment, current_user))
        .order_by(APIEnvironment.name)
    )

    if collection_id:
        query = query.where(APIEnvironment.collection_id == collection_id)

    result = await db.execute(query)
    environments = result.scalars().all()

    summaries = []
    for env in environments:
        var_count = len(env.variables) if env.variables else 0
        summaries.append(APIEnvironmentSummary(
            id=env.id,
            name=env.name,
            description=env.description,
            collection_id=env.collection_id,
            is_default=env.is_default,
            variable_count=var_count,
        ))

    return summaries


@router.post("", response_model=APIEnvironmentResponse)
async def create_environment(
    data: APIEnvironmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API environment."""
    # If collection_id provided, verify access
    if data.collection_id:
        collection_result = await db.execute(
            select(APICollection)
            .where(
                APICollection.id == data.collection_id,
                tenant_filter(APICollection, current_user),
            )
        )
        if not collection_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Collection not found")

    # If setting as default, unset other defaults
    if data.is_default:
        query = (
            select(APIEnvironment)
            .where(tenant_filter(APIEnvironment, current_user))
        )
        if data.collection_id:
            query = query.where(APIEnvironment.collection_id == data.collection_id)

        result = await db.execute(query)
        for env in result.scalars().all():
            env.is_default = False

    environment = APIEnvironment(
        name=data.name,
        description=data.description,
        collection_id=data.collection_id,
        variables=data.variables if data.variables else None,
        base_url=data.base_url,
        auth_config=data.auth_config,
        default_headers=data.default_headers,
        is_default=data.is_default,
    )
    set_tenant(environment, current_user)

    db.add(environment)
    await db.commit()
    await db.refresh(environment)

    return APIEnvironmentResponse.model_validate(environment)


@router.get("/{environment_id}", response_model=APIEnvironmentResponse)
async def get_environment(
    environment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get an API environment."""
    result = await db.execute(
        select(APIEnvironment)
        .where(
            APIEnvironment.id == environment_id,
            tenant_filter(APIEnvironment, current_user),
        )
    )
    environment = result.scalar_one_or_none()

    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")

    return APIEnvironmentResponse.model_validate(environment)


@router.patch("/{environment_id}", response_model=APIEnvironmentResponse)
async def update_environment(
    environment_id: UUID,
    data: APIEnvironmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an API environment."""
    result = await db.execute(
        select(APIEnvironment)
        .where(
            APIEnvironment.id == environment_id,
            tenant_filter(APIEnvironment, current_user),
        )
    )
    environment = result.scalar_one_or_none()

    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")

    # If setting as default, unset other defaults
    if data.is_default:
        query = (
            select(APIEnvironment)
            .where(
                tenant_filter(APIEnvironment, current_user),
                APIEnvironment.id != environment_id,
            )
        )
        if environment.collection_id:
            query = query.where(APIEnvironment.collection_id == environment.collection_id)

        others = await db.execute(query)
        for env in others.scalars().all():
            env.is_default = False

    # Update fields
    if data.name is not None:
        environment.name = data.name
    if data.description is not None:
        environment.description = data.description
    if data.variables is not None:
        environment.variables = data.variables
    if data.base_url is not None:
        environment.base_url = data.base_url
    if data.auth_config is not None:
        environment.auth_config = data.auth_config
    if data.default_headers is not None:
        environment.default_headers = data.default_headers
    if data.is_default is not None:
        environment.is_default = data.is_default

    await db.commit()
    await db.refresh(environment)

    return APIEnvironmentResponse.model_validate(environment)


@router.delete("/{environment_id}")
async def delete_environment(
    environment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an API environment."""
    result = await db.execute(
        select(APIEnvironment)
        .where(
            APIEnvironment.id == environment_id,
            tenant_filter(APIEnvironment, current_user),
        )
    )
    environment = result.scalar_one_or_none()

    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")

    await db.delete(environment)
    await db.commit()

    return {"status": "deleted"}


@router.post("/{environment_id}/clone", response_model=APIEnvironmentResponse)
async def clone_environment(
    environment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clone an API environment."""
    result = await db.execute(
        select(APIEnvironment)
        .where(
            APIEnvironment.id == environment_id,
            tenant_filter(APIEnvironment, current_user),
        )
    )
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(status_code=404, detail="Environment not found")

    clone = APIEnvironment(
        name=f"{original.name} (Copy)",
        description=original.description,
        collection_id=original.collection_id,
        variables=original.variables,
        base_url=original.base_url,
        auth_config=original.auth_config,
        default_headers=original.default_headers,
        is_default=False,  # Don't clone default status
    )
    set_tenant(clone, current_user)

    db.add(clone)
    await db.commit()
    await db.refresh(clone)

    return APIEnvironmentResponse.model_validate(clone)
