from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.db.postgres import get_db
from app.models.test import Test, TestVersion, Step, Collection
from app.models.run import Run
from app.models.user import User
from app.schemas.test import (
    TestCreate, TestUpdate, TestResponse, TestListResponse, TestVersionResponse,
    GenerateVariantsRequest, GenerateVariantsResponse, VariantResponse
)
from app.schemas.step import StepReorder, StepUpdate
from app.services.playwright_generator import generate_playwright_test, generate_playwright_python
from app.services.variant_generator import VariantGenerator
from app.security import get_current_user
from app.utils.tenant import tenant_filter, set_tenant

router = APIRouter()


@router.get("", response_model=list[TestListResponse])
async def list_tests(
    collection_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(Test)
        .where(tenant_filter(Test, current_user))
        .options(selectinload(Test.collection))
        .order_by(Test.updated_at.desc())
    )

    if collection_id:
        query = query.where(Test.collection_id == collection_id)

    result = await db.execute(query)
    tests = result.scalars().all()

    response = []
    for test in tests:
        version_count_result = await db.execute(
            select(func.count(TestVersion.id)).where(TestVersion.test_id == test.id)
        )
        version_count = version_count_result.scalar() or 0

        latest_run_result = await db.execute(
            select(Run)
            .join(TestVersion)
            .where(TestVersion.test_id == test.id)
            .order_by(Run.started_at.desc())
            .limit(1)
        )
        latest_run = latest_run_result.scalar_one_or_none()

        collection_info = None
        if test.collection:
            collection_info = {
                "id": test.collection.id,
                "name": test.collection.name,
                "color": test.collection.color
            }

        response.append(TestListResponse(
            id=test.id,
            name=test.name,
            description=test.description,
            target_url=test.target_url,
            collection_id=test.collection_id,
            collection=collection_info,
            created_at=test.created_at,
            version_count=version_count,
            last_run_status=latest_run.status if latest_run else None
        ))

    return response


@router.post("", response_model=TestResponse)
async def create_test(
    test_data: TestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    test = Test(
        name=test_data.name,
        description=test_data.description,
        target_url=test_data.target_url,
        collection_id=test_data.collection_id
    )
    set_tenant(test, current_user)
    db.add(test)
    await db.flush()

    version = TestVersion(test_id=test.id, version_number=1)
    db.add(version)
    await db.flush()

    for step_data in test_data.steps:
        step = Step(
            version_id=version.id,
            order_index=step_data.order_index,
            type=step_data.type,
            selector=step_data.selector,
            value=step_data.value,
            screenshot_url=step_data.screenshot_url,
            assertion_config=step_data.assertion_config.model_dump() if step_data.assertion_config else None
        )
        db.add(step)

    await db.commit()
    await db.refresh(test)

    return await get_test(test.id, current_user, db)


@router.get("/{test_id}", response_model=TestResponse)
async def get_test(
    test_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
    )
    test = result.scalar_one_or_none()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    version_result = await db.execute(
        select(TestVersion)
        .where(TestVersion.test_id == test_id)
        .order_by(TestVersion.version_number.desc())
        .limit(1)
    )
    latest_version = version_result.scalar_one_or_none()

    latest_version_response = None
    if latest_version:
        steps_result = await db.execute(
            select(Step)
            .where(Step.version_id == latest_version.id)
            .order_by(Step.order_index)
        )
        steps = steps_result.scalars().all()

        latest_version_response = TestVersionResponse(
            id=latest_version.id,
            version_number=latest_version.version_number,
            created_at=latest_version.created_at,
            steps=steps
        )

    return TestResponse(
        id=test.id,
        name=test.name,
        description=test.description,
        target_url=test.target_url,
        created_at=test.created_at,
        updated_at=test.updated_at,
        latest_version=latest_version_response
    )


@router.patch("/{test_id}", response_model=TestResponse)
async def update_test(
    test_id: UUID,
    test_data: TestUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
    )
    test = result.scalar_one_or_none()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if test_data.name is not None:
        test.name = test_data.name
    if test_data.description is not None:
        test.description = test_data.description
    if test_data.target_url is not None:
        test.target_url = test_data.target_url
    if test_data.collection_id is not None:
        test.collection_id = test_data.collection_id

    await db.commit()
    return await get_test(test_id, current_user, db)


@router.delete("/{test_id}")
async def delete_test(
    test_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
    )
    test = result.scalar_one_or_none()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    await db.delete(test)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{test_id}/versions", response_model=TestVersionResponse)
async def create_version(
    test_id: UUID,
    steps: list[dict],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new version of the test with updated steps."""
    result = await db.execute(
        select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
    )
    test = result.scalar_one_or_none()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    version_result = await db.execute(
        select(func.max(TestVersion.version_number)).where(TestVersion.test_id == test_id)
    )
    max_version = version_result.scalar() or 0

    version = TestVersion(test_id=test_id, version_number=max_version + 1)
    db.add(version)
    await db.flush()

    for idx, step_data in enumerate(steps):
        step = Step(
            version_id=version.id,
            order_index=idx,
            type=step_data["type"],
            selector=step_data.get("selector"),
            value=step_data.get("value"),
            screenshot_url=step_data.get("screenshot_url"),
            assertion_config=step_data.get("assertion_config")
        )
        db.add(step)

    await db.commit()
    await db.refresh(version)

    steps_result = await db.execute(
        select(Step).where(Step.version_id == version.id).order_by(Step.order_index)
    )

    return TestVersionResponse(
        id=version.id,
        version_number=version.version_number,
        created_at=version.created_at,
        steps=steps_result.scalars().all()
    )


@router.get("/{test_id}/playwright", response_class=PlainTextResponse)
async def get_playwright_code(
    test_id: UUID,
    language: str = "typescript",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate Playwright test code for this test."""
    result = await db.execute(
        select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
    )
    test = result.scalar_one_or_none()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    version_result = await db.execute(
        select(TestVersion)
        .where(TestVersion.test_id == test_id)
        .order_by(TestVersion.version_number.desc())
        .limit(1)
    )
    latest_version = version_result.scalar_one_or_none()

    if not latest_version:
        raise HTTPException(status_code=404, detail="No version found")

    steps_result = await db.execute(
        select(Step)
        .where(Step.version_id == latest_version.id)
        .order_by(Step.order_index)
    )
    steps = steps_result.scalars().all()

    # Convert to dict for generator (same at line 375 for generate_variants)
    steps_data = [
        {
            "type": step.type,
            "selector": step.selector,
            "value": step.value,
            "assertion_config": step.assertion_config,
        }
        for step in steps
    ]

    if language == "python":
        return generate_playwright_python(test.name, steps_data, test.target_url)
    else:
        return generate_playwright_test(test.name, steps_data, test.target_url)


@router.post("/{test_id}/generate-variants")
async def generate_variants(
    test_id: UUID,
    request: GenerateVariantsRequest = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate test variants from recorded steps using LLM analysis.

    Smart features:
    - Detects setup (login) vs test portions - only generates variants for test portion
    - Deduplicates - won't regenerate variants for identical step patterns
    """
    result = await db.execute(
        select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
    )
    test = result.scalar_one_or_none()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    # Get latest version with steps
    version_result = await db.execute(
        select(TestVersion)
        .where(TestVersion.test_id == test_id)
        .order_by(TestVersion.version_number.desc())
        .limit(1)
    )
    latest_version = version_result.scalar_one_or_none()

    if not latest_version:
        raise HTTPException(status_code=404, detail="No version found")

    steps_result = await db.execute(
        select(Step)
        .where(Step.version_id == latest_version.id)
        .order_by(Step.order_index)
    )
    steps = steps_result.scalars().all()

    if not steps:
        raise HTTPException(status_code=400, detail="No steps found to generate variants from")

    # Convert steps to dict format for variant generator
    steps_data = [
        {
            "type": step.type,
            "selector": step.selector,
            "value": step.value,
            "selector_info": step.assertion_config or {},
        }
        for step in steps
    ]

    # Generate variants using LLM
    generator = VariantGenerator()
    variant_types = request.variant_types if request else None

    result = await generator.generate_variants(
        steps=steps_data,
        variant_types=variant_types,
        test_name=test.name,
        test_description=test.description or "",
    )

    variants = result.get("variants", [])

    # Run error discovery to get actual error messages
    if variants:
        from app.services.error_discoverer import ErrorDiscoverer
        discoverer = ErrorDiscoverer()
        variants = await discoverer.discover_errors(variants, test.target_url)

    return {
        "test_id": str(test.id),
        "test_name": test.name,
        "variants": [VariantResponse(**v) for v in variants],
        "setup_boundary": result.get("setup_boundary", 0),
        "setup_type": result.get("setup_type", "none"),
        "setup_variants_skipped": result.get("setup_variants_skipped", False),
        "duplicate_skipped": result.get("duplicate_skipped", False),
    }


from pydantic import BaseModel as PydanticBaseModel


class SaveVariantsRequest(PydanticBaseModel):
    variants: list[dict]  # List of variant objects with name, type, steps, expected_result


@router.post("/{test_id}/save-variants")
async def save_variants(
    test_id: UUID,
    request: SaveVariantsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Save generated variants as new test entries."""
    result = await db.execute(
        select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
    )
    parent_test = result.scalar_one_or_none()

    if not parent_test:
        raise HTTPException(status_code=404, detail="Test not found")

    saved_variants = []

    for variant in request.variants:
        variant_test = Test(
            name=f"{parent_test.name} - {variant.get('name', 'Variant')}",
            description=variant.get('description', ''),
            target_url=parent_test.target_url,
            collection_id=parent_test.collection_id,
            parent_test_id=parent_test.id,
            variant_type=variant.get('type', 'negative'),
            expected_result=variant.get('expected_result', ''),
            user_id=current_user.id,
            org_id=current_user.org_id,
        )
        db.add(variant_test)
        await db.flush()

        version = TestVersion(
            test_id=variant_test.id,
            version_number=1,
        )
        db.add(version)
        await db.flush()

        steps = variant.get('steps', [])
        for i, step_data in enumerate(steps):
            step = Step(
                version_id=version.id,
                order_index=i,
                type=step_data.get('type', ''),
                selector=step_data.get('selector'),
                value=step_data.get('value'),
                assertion_config=step_data.get('assertion_config'),
            )
            db.add(step)

        saved_variants.append({
            "id": str(variant_test.id),
            "name": variant_test.name,
            "type": variant_test.variant_type,
        })

    await db.commit()

    return {
        "saved": len(saved_variants),
        "variants": saved_variants,
    }


@router.delete("/{test_id}/steps/{step_id}")
async def delete_step(
    test_id: UUID,
    step_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a step from the latest version of a test."""
    result = await db.execute(
        select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
    )
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    step_result = await db.execute(select(Step).where(Step.id == step_id))
    step = step_result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    await db.delete(step)

    # Reorder remaining steps
    remaining_steps = await db.execute(
        select(Step)
        .where(Step.version_id == step.version_id)
        .order_by(Step.order_index)
    )
    for idx, s in enumerate(remaining_steps.scalars().all()):
        s.order_index = idx

    await db.commit()
    return {"status": "deleted", "step_id": str(step_id)}


@router.patch("/{test_id}/steps/{step_id}")
async def update_step(
    test_id: UUID,
    step_id: UUID,
    step_data: StepUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a step in a test."""
    result = await db.execute(
        select(Test).where(Test.id == test_id, tenant_filter(Test, current_user))
    )
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    step_result = await db.execute(select(Step).where(Step.id == step_id))
    step = step_result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if step_data.type is not None:
        step.type = step_data.type
    if step_data.selector is not None:
        step.selector = step_data.selector
    if step_data.value is not None:
        step.value = step_data.value
    if step_data.assertion_config is not None:
        step.assertion_config = step_data.assertion_config.model_dump()

    await db.commit()
    await db.refresh(step)
    return step
