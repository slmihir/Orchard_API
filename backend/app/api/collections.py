from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.db.postgres import get_db
from app.models.test import Collection, Test
from app.models.user import User
from app.schemas.collection import CollectionCreate, CollectionUpdate, CollectionResponse
from app.security import get_current_user
from app.utils.tenant import tenant_filter, set_tenant

router = APIRouter()


@router.get("", response_model=list[CollectionResponse])
async def list_collections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Collection)
        .where(tenant_filter(Collection, current_user))
        .order_by(Collection.name)
    )
    collections = result.scalars().all()

    response = []
    for collection in collections:
        test_count_result = await db.execute(
            select(func.count(Test.id)).where(Test.collection_id == collection.id)
        )
        test_count = test_count_result.scalar() or 0

        response.append(CollectionResponse(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            color=collection.color,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
            test_count=test_count
        ))

    return response


@router.post("", response_model=CollectionResponse)
async def create_collection(
    data: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    collection = Collection(
        name=data.name,
        description=data.description,
        color=data.color
    )
    set_tenant(collection, current_user)
    db.add(collection)
    await db.commit()
    await db.refresh(collection)

    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        color=collection.color,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        test_count=0
    )


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Collection).where(
            Collection.id == collection_id,
            tenant_filter(Collection, current_user)
        )
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    test_count_result = await db.execute(
        select(func.count(Test.id)).where(Test.collection_id == collection.id)
    )
    test_count = test_count_result.scalar() or 0

    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        color=collection.color,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        test_count=test_count
    )


@router.patch("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: UUID,
    data: CollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Collection).where(
            Collection.id == collection_id,
            tenant_filter(Collection, current_user)
        )
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if data.name is not None:
        collection.name = data.name
    if data.description is not None:
        collection.description = data.description
    if data.color is not None:
        collection.color = data.color

    await db.commit()
    await db.refresh(collection)

    return await get_collection(collection_id, current_user, db)


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Collection).where(
            Collection.id == collection_id,
            tenant_filter(Collection, current_user)
        )
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Unassign tests from this collection
    await db.execute(
        Test.__table__.update()
        .where(Test.collection_id == collection_id)
        .values(collection_id=None)
    )

    await db.delete(collection)
    await db.commit()
    return {"status": "deleted"}
