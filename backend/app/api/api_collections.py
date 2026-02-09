"""API Collections CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from uuid import UUID
import json

from app.db.postgres import get_db
from app.models.api_collection import APICollection
from app.models.api_request import APIRequest
from app.models.api_environment import APIEnvironment
from app.models.user import User
from app.schemas.api_collection import (
    APICollectionCreate,
    APICollectionUpdate,
    APICollectionResponse,
    APICollectionSummary,
    APICollectionDetailResponse,
)
from app.security import get_current_user
from app.utils.tenant import tenant_filter, set_tenant
from app.services.api_testing.importers import PostmanImporter, OpenAPIImporter

router = APIRouter()


@router.get("", response_model=list[APICollectionSummary])
async def list_collections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API collections for the current tenant."""
    query = (
        select(APICollection)
        .where(tenant_filter(APICollection, current_user))
        .order_by(APICollection.updated_at.desc())
    )

    result = await db.execute(query)
    collections = result.scalars().all()

    # Get counts for each collection
    summaries = []
    for collection in collections:
        # Count requests
        request_count = await db.execute(
            select(func.count(APIRequest.id))
            .where(APIRequest.collection_id == collection.id)
        )

        # Count environments
        env_count = await db.execute(
            select(func.count(APIEnvironment.id))
            .where(APIEnvironment.collection_id == collection.id)
        )

        summaries.append(APICollectionSummary(
            id=collection.id,
            name=collection.name,
            description=collection.description,
            base_url=collection.base_url,
            default_engine=collection.default_engine,
            import_source=collection.import_source,
            request_count=request_count.scalar() or 0,
            environment_count=env_count.scalar() or 0,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        ))

    return summaries


@router.post("", response_model=APICollectionResponse)
async def create_collection(
    data: APICollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API collection."""
    # Serialize Pydantic models to dicts for JSONB storage
    variables_dict = None
    if data.variables:
        variables_dict = {k: v.model_dump() for k, v in data.variables.items()}

    collection = APICollection(
        name=data.name,
        description=data.description,
        base_url=data.base_url,
        auth_config=data.auth_config.model_dump() if data.auth_config else None,
        variables=variables_dict,
        default_headers=data.default_headers,
        default_engine=data.default_engine,
    )
    set_tenant(collection, current_user)

    db.add(collection)
    await db.commit()
    await db.refresh(collection)

    return APICollectionResponse.model_validate(collection)


@router.get("/{collection_id}", response_model=APICollectionDetailResponse)
async def get_collection(
    collection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a collection with its requests and environments."""
    result = await db.execute(
        select(APICollection)
        .where(
            APICollection.id == collection_id,
            tenant_filter(APICollection, current_user),
        )
        .options(
            selectinload(APICollection.requests),
            selectinload(APICollection.environments),
        )
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Sort requests by order_index
    sorted_requests = sorted(collection.requests, key=lambda r: r.order_index)

    return APICollectionDetailResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        base_url=collection.base_url,
        auth_config=collection.auth_config,
        variables=collection.variables,
        default_headers=collection.default_headers,
        default_engine=collection.default_engine,
        import_source=collection.import_source,
        import_source_id=collection.import_source_id,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        requests=sorted_requests,
        environments=collection.environments,
    )


@router.patch("/{collection_id}", response_model=APICollectionResponse)
async def update_collection(
    collection_id: UUID,
    data: APICollectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an API collection."""
    result = await db.execute(
        select(APICollection)
        .where(
            APICollection.id == collection_id,
            tenant_filter(APICollection, current_user),
        )
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Update fields
    if data.name is not None:
        collection.name = data.name
    if data.description is not None:
        collection.description = data.description
    if data.base_url is not None:
        collection.base_url = data.base_url
    if data.auth_config is not None:
        collection.auth_config = data.auth_config.model_dump()
    if data.variables is not None:
        collection.variables = data.variables
    if data.default_headers is not None:
        collection.default_headers = data.default_headers
    if data.default_engine is not None:
        collection.default_engine = data.default_engine

    await db.commit()
    await db.refresh(collection)

    return APICollectionResponse.model_validate(collection)


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an API collection and all its contents."""
    result = await db.execute(
        select(APICollection)
        .where(
            APICollection.id == collection_id,
            tenant_filter(APICollection, current_user),
        )
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    await db.delete(collection)
    await db.commit()

    return {"status": "deleted"}


@router.post("/import/postman", response_model=APICollectionResponse)
async def import_postman(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import a Postman collection."""
    content = await file.read()

    try:
        collection_data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    importer = PostmanImporter()
    collection_dict, requests_list, _ = importer.import_collection(
        collection_data,
        user_id=str(current_user.id),
        org_id=str(current_user.org_id) if current_user.org_id else None,
    )

    # Create collection
    collection = APICollection(
        name=collection_dict["name"],
        description=collection_dict["description"],
        base_url=collection_dict["base_url"],
        auth_config=collection_dict["auth_config"],
        variables=collection_dict["variables"],
        default_headers=collection_dict["default_headers"],
        default_engine=collection_dict["default_engine"],
        import_source="postman",
        import_source_id=collection_dict.get("import_source_id"),
    )
    set_tenant(collection, current_user)
    db.add(collection)
    await db.flush()

    # Create requests
    for req_dict in requests_list:
        request = APIRequest(
            collection_id=collection.id,
            name=req_dict["name"],
            description=req_dict.get("description"),
            order_index=req_dict.get("order_index", 0),
            method=req_dict["method"],
            url_path=req_dict["url_path"],
            headers=req_dict.get("headers"),
            query_params=req_dict.get("query_params"),
            body=req_dict.get("body"),
            assertions=req_dict.get("assertions"),
            variable_extractions=req_dict.get("variable_extractions"),
            folder_path=req_dict.get("folder_path"),
        )
        db.add(request)

    await db.commit()
    await db.refresh(collection)

    return APICollectionResponse.model_validate(collection)


@router.post("/import/openapi", response_model=APICollectionResponse)
async def import_openapi(
    file: UploadFile = File(...),
    generate_assertions: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import an OpenAPI/Swagger specification."""
    content = await file.read()
    content_str = content.decode("utf-8")

    importer = OpenAPIImporter()

    try:
        collection_dict, requests_list = importer.import_spec(
            content_str,
            user_id=str(current_user.id),
            org_id=str(current_user.org_id) if current_user.org_id else None,
            generate_assertions=generate_assertions,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse specification: {str(e)}")

    # Create collection
    collection = APICollection(
        name=collection_dict["name"],
        description=collection_dict["description"],
        base_url=collection_dict["base_url"],
        auth_config=collection_dict["auth_config"],
        variables=collection_dict["variables"],
        default_headers=collection_dict["default_headers"],
        default_engine=collection_dict["default_engine"],
        import_source="openapi",
    )
    set_tenant(collection, current_user)
    db.add(collection)
    await db.flush()

    # Create requests
    for req_dict in requests_list:
        request = APIRequest(
            collection_id=collection.id,
            name=req_dict["name"],
            description=req_dict.get("description"),
            order_index=req_dict.get("order_index", 0),
            method=req_dict["method"],
            url_path=req_dict["url_path"],
            headers=req_dict.get("headers"),
            query_params=req_dict.get("query_params"),
            body=req_dict.get("body"),
            assertions=req_dict.get("assertions"),
            variable_extractions=req_dict.get("variable_extractions"),
            folder_path=req_dict.get("folder_path"),
        )
        db.add(request)

    await db.commit()
    await db.refresh(collection)

    return APICollectionResponse.model_validate(collection)


@router.get("/{collection_id}/export/karate")
async def export_to_karate(
    collection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export collection as Karate .feature file."""
    from app.services.api_testing.karate import KarateConverter

    result = await db.execute(
        select(APICollection)
        .where(
            APICollection.id == collection_id,
            tenant_filter(APICollection, current_user),
        )
        .options(selectinload(APICollection.requests))
    )
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Convert to dicts
    collection_dict = {
        "name": collection.name,
        "description": collection.description,
        "base_url": collection.base_url,
        "auth_config": collection.auth_config,
        "default_headers": collection.default_headers,
    }

    requests_list = [
        {
            "name": r.name,
            "description": r.description,
            "method": r.method,
            "url_path": r.url_path,
            "headers": r.headers,
            "query_params": r.query_params,
            "body": r.body,
            "assertions": r.assertions,
            "variable_extractions": r.variable_extractions,
            "folder_path": r.folder_path,
        }
        for r in sorted(collection.requests, key=lambda x: x.order_index)
    ]

    converter = KarateConverter()
    feature_content = converter.requests_to_feature(requests_list, collection_dict)

    return {
        "filename": f"{collection.name.lower().replace(' ', '_')}.feature",
        "content": feature_content,
    }
