"""AI-powered API test generation routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel

from app.db.postgres import get_db
from app.models.api_collection import APICollection
from app.models.api_request import APIRequest
from app.models.user import User
from app.security import get_current_user
from app.utils.tenant import tenant_filter
from app.services.api_testing.ai import APITestGenerator

router = APIRouter()


class GenerateFromNLRequest(BaseModel):
    """Request to generate tests from natural language."""
    prompt: str
    collection_id: UUID | None = None
    max_tests: int = 5


class SuggestAssertionsRequest(BaseModel):
    """Request to suggest assertions for a request."""
    request_id: UUID
    sample_response: dict | None = None
    response_status: int | None = None


class ImproveTestRequest(BaseModel):
    """Request to improve an existing test."""
    request_id: UUID
    improvement_type: str = "comprehensive"  # comprehensive, security, performance


class GenerateNegativeTestsRequest(BaseModel):
    """Request to generate negative tests from a positive test."""
    request_id: UUID
    max_tests: int = 3


@router.post("/from-natural-language")
async def generate_from_natural_language(
    data: GenerateFromNLRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate API tests from natural language description."""
    # Get collection context if provided
    base_url = None
    existing_variables = []

    if data.collection_id:
        result = await db.execute(
            select(APICollection)
            .where(
                APICollection.id == data.collection_id,
                tenant_filter(APICollection, current_user),
            )
        )
        collection = result.scalar_one_or_none()

        if collection:
            base_url = collection.base_url
            if collection.variables:
                existing_variables = list(collection.variables.keys())

    generator = APITestGenerator()

    try:
        tests = await generator.from_natural_language(
            prompt=data.prompt,
            base_url=base_url,
            existing_variables=existing_variables,
            max_tests=data.max_tests,
        )

        return {
            "tests": tests,
            "count": len(tests),
            "prompt": data.prompt,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/suggest-assertions")
async def suggest_assertions(
    data: SuggestAssertionsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Suggest assertions for an existing request."""
    # Load request
    result = await db.execute(
        select(APIRequest)
        .join(APICollection)
        .where(
            APIRequest.id == data.request_id,
            tenant_filter(APICollection, current_user),
        )
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    generator = APITestGenerator()

    try:
        assertions = await generator.suggest_assertions(
            method=request.method,
            url_path=request.url_path,
            sample_response=data.sample_response,
            response_status=data.response_status,
        )

        return {
            "assertions": assertions,
            "count": len(assertions),
            "request_id": str(data.request_id),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestion failed: {str(e)}")


@router.post("/improve-test")
async def improve_test(
    data: ImproveTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Improve an existing test with additional assertions or coverage."""
    # Load request
    result = await db.execute(
        select(APIRequest)
        .join(APICollection)
        .where(
            APIRequest.id == data.request_id,
            tenant_filter(APICollection, current_user),
        )
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    test_dict = {
        "name": request.name,
        "description": request.description,
        "method": request.method,
        "url_path": request.url_path,
        "headers": request.headers,
        "query_params": request.query_params,
        "body": request.body,
        "assertions": request.assertions,
        "variable_extractions": request.variable_extractions,
    }

    generator = APITestGenerator()

    try:
        improved = await generator.improve_test(
            test=test_dict,
            improvement_type=data.improvement_type,
        )

        return {
            "improved_test": improved,
            "request_id": str(data.request_id),
            "improvement_type": data.improvement_type,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Improvement failed: {str(e)}")


@router.post("/generate-negative-tests")
async def generate_negative_tests(
    data: GenerateNegativeTestsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate negative test cases from a positive test."""
    # Load request
    result = await db.execute(
        select(APIRequest)
        .join(APICollection)
        .where(
            APIRequest.id == data.request_id,
            tenant_filter(APICollection, current_user),
        )
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    positive_test = {
        "name": request.name,
        "description": request.description,
        "method": request.method,
        "url_path": request.url_path,
        "headers": request.headers,
        "query_params": request.query_params,
        "body": request.body,
        "assertions": request.assertions,
    }

    generator = APITestGenerator()

    try:
        negative_tests = await generator.generate_negative_tests(
            positive_test=positive_test,
            max_tests=data.max_tests,
        )

        return {
            "negative_tests": negative_tests,
            "count": len(negative_tests),
            "source_request_id": str(data.request_id),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/from-openapi")
async def generate_from_openapi(
    spec_content: str,
    collection_id: UUID | None = None,
    generate_negative: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate comprehensive tests from OpenAPI specification using AI."""
    from app.services.api_testing.importers import OpenAPIImporter

    # First, import the OpenAPI spec
    importer = OpenAPIImporter()

    try:
        _, requests = importer.import_spec(
            spec_content,
            generate_assertions=True,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid OpenAPI spec: {str(e)}")

    # If AI enhancement is requested, improve each test
    if generate_negative:
        generator = APITestGenerator()
        enhanced_requests = []

        for req in requests:
            try:
                # Generate negative tests for each endpoint
                negative_tests = await generator.generate_negative_tests(
                    positive_test=req,
                    max_tests=2,
                )
                enhanced_requests.append(req)
                enhanced_requests.extend(negative_tests)
            except Exception:
                # If AI fails, just use the original
                enhanced_requests.append(req)

        requests = enhanced_requests

    return {
        "tests": requests,
        "count": len(requests),
        "ai_enhanced": generate_negative,
    }
