"""Projects API - CRUD and discovery WebSocket."""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
import asyncio

from app.db.postgres import get_db, AsyncSessionLocal
from app.models.project import Project, DiscoveredPage, PageConnection
from app.models.test_case import TestCase, TestRun
from app.services.test_case_service import TestCaseService
from app.models.user import User
from app.services.scout_agent import ScoutAgent
from app.security import get_current_user
from app.utils.tenant import tenant_filter
from app.config import get_settings
from app.services.variant_generator import VariantGenerator
from jose import jwt, JWTError

config = get_settings()
router = APIRouter()


# Pydantic schemas
class ProjectCreate(BaseModel):
    name: str
    base_url: str
    description: str | None = None
    credentials: dict | None = None
    max_depth: int = 5
    max_pages: int = 100


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    credentials: dict | None = None
    max_depth: int | None = None
    max_pages: int | None = None


class DiscoveredPageResponse(BaseModel):
    id: UUID
    url: str
    path: str
    title: str | None
    page_type: str | None
    section: str | None
    screenshot_url: str | None
    depth: int
    is_feature: bool
    feature_name: str | None
    is_pattern_instance: bool
    pattern_id: str | None
    graph_x: float | None
    graph_y: float | None
    graph_z: float | None
    discovered_at: datetime

    class Config:
        from_attributes = True


class PageConnectionResponse(BaseModel):
    id: UUID
    source_page_id: UUID
    target_page_id: UUID
    action_type: str
    action_text: str | None

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    base_url: str
    description: str | None
    status: str
    max_depth: int
    max_pages: int
    pages_discovered: int
    features_found: int
    patterns_detected: int
    discovery_started_at: datetime | None
    discovery_completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailResponse(ProjectResponse):
    pages: list[DiscoveredPageResponse]
    connections: list[PageConnectionResponse]


# REST endpoints
@router.post("", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new project."""
    project = Project(
        name=data.name,
        base_url=data.base_url,
        description=data.description,
        credentials=data.credentials,
        max_depth=data.max_depth,
        max_pages=data.max_pages,
        user_id=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all projects."""
    result = await db.execute(
        select(Project)
        .where(tenant_filter(Project, current_user))
        .order_by(Project.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get project with all discovered pages and connections."""
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.pages),
            selectinload(Project.connections)
        )
        .where(Project.id == project_id, tenant_filter(Project, current_user))
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a project."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, tenant_filter(Project, current_user))
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a project and all its discovered data."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, tenant_filter(Project, current_user))
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()
    return {"status": "deleted"}


@router.get("/{project_id}/graph")
async def get_project_graph(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get graph data optimized for force-graph visualization."""
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.pages),
            selectinload(Project.connections)
        )
        .where(Project.id == project_id, tenant_filter(Project, current_user))
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    nodes = []
    for page in project.pages:
        nodes.append({
            "id": str(page.id),
            "url": page.url,
            "path": page.path,
            "title": page.title or page.path,
            "type": page.page_type or "page",
            "section": page.section,
            "depth": page.depth,
            "isFeature": page.is_feature,
            "featureName": page.feature_name,
            "featureDescription": page.feature_description,
            "isPattern": page.is_pattern_instance,
            "patternId": page.pattern_id,
            "screenshot": page.screenshot_url,
            "x": page.graph_x,
            "y": page.graph_y,
            "z": page.graph_z,
            # Rich LLM analysis data
            "requiresAuth": page.requires_auth,
            "requiredPermissions": page.required_permissions,
            "llmAnalysis": page.llm_analysis,
            "testScenarios": page.test_scenarios,
            "formsFound": page.forms_found,
            "actionsFound": page.actions_found,
            "tablesFound": page.tables_found,
        })

    links = []
    for conn in project.connections:
        links.append({
            "source": str(conn.source_page_id),
            "target": str(conn.target_page_id),
            "type": conn.action_type,
            "label": conn.action_text,
        })

    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "pages": project.pages_discovered,
            "features": project.features_found,
            "patterns": project.patterns_detected,
        }
    }


# WebSocket for real-time discovery
async def get_user_from_token(token: str, db) -> User | None:
    """Get user from JWT token."""
    try:
        payload = jwt.decode(token, config.secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            return None

        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except JWTError:
        return None


@router.websocket("/ws/{project_id}/discover")
async def discover_project_websocket(websocket: WebSocket, project_id: str, token: str = None):
    """WebSocket endpoint for real-time project discovery."""
    await websocket.accept()

    try:
        async with AsyncSessionLocal() as db:
            # Authenticate
            current_user = None
            if token:
                current_user = await get_user_from_token(token, db)

            if not current_user:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Unauthorized"}
                })
                return

            result = await db.execute(
                select(Project)
                .where(Project.id == project_id, tenant_filter(Project, current_user))
            )
            project = result.scalar_one_or_none()

            if not project:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Project not found"}
                })
                return

            # Clear existing discovered data for re-discovery
            await db.execute(
                PageConnection.__table__.delete().where(
                    PageConnection.project_id == project.id
                )
            )
            await db.execute(
                DiscoveredPage.__table__.delete().where(
                    DiscoveredPage.project_id == project.id
                )
            )

            project.status = "discovering"
            project.discovery_started_at = datetime.utcnow()
            project.pages_discovered = 0
            project.features_found = 0
            project.patterns_detected = 0
            await db.commit()

        # Callbacks for real-time updates
        async def on_page_discovered(page_data: dict):
            """Called when a new page is discovered."""
            await websocket.send_json({
                "type": "page_discovered",
                "data": page_data
            })

        async def on_connection_found(connection_data: dict):
            """Called when a connection between pages is found."""
            await websocket.send_json({
                "type": "connection_found",
                "data": connection_data
            })

        async def on_screenshot(screenshot_data: dict):
            """Called with live browser screenshot."""
            await websocket.send_json({
                "type": "screenshot",
                "data": screenshot_data
            })

        async def on_activity(activity: dict):
            """Called for activity log updates."""
            await websocket.send_json({
                "type": "activity",
                "data": activity
            })

        async def on_stats_update(stats: dict):
            """Called when stats are updated."""
            await websocket.send_json({
                "type": "stats",
                "data": stats
            })

        async def on_section_found(section: dict):
            """Called when a new section is identified."""
            await websocket.send_json({
                "type": "section_found",
                "data": section
            })

        async def on_feature_found(feature: dict):
            """Called when a feature is identified."""
            await websocket.send_json({
                "type": "feature_found",
                "data": feature
            })

        async def on_pattern_detected(pattern: dict):
            """Called when a pattern is detected."""
            await websocket.send_json({
                "type": "pattern_detected",
                "data": pattern
            })

        scout = ScoutAgent(
            project_id=project_id,
            base_url=project.base_url,
            credentials=project.credentials,
            max_depth=project.max_depth,
            max_pages=project.max_pages,
            on_page_discovered=on_page_discovered,
            on_connection_found=on_connection_found,
            on_screenshot=on_screenshot,
            on_activity=on_activity,
            on_stats_update=on_stats_update,
            on_section_found=on_section_found,
            on_feature_found=on_feature_found,
            on_pattern_detected=on_pattern_detected,
        )

        await websocket.send_json({
            "type": "status",
            "data": {"status": "starting", "project_id": project_id}
        })

        # Run discovery in a task so we can listen for control messages
        async def run_discovery():
            return await scout.discover()

        discovery_task = asyncio.create_task(run_discovery())

        # Listen for control messages (pause, resume, stop)
        async def listen_for_messages():
            try:
                while not discovery_task.done():
                    try:
                        message = await asyncio.wait_for(websocket.receive_json(), timeout=0.5)
                        msg_type = message.get("type")

                        if msg_type == "pause":
                            scout.pause()
                            await websocket.send_json({
                                "type": "status",
                                "data": {"status": "paused"}
                            })
                        elif msg_type == "resume":
                            scout.resume()
                            await websocket.send_json({
                                "type": "status",
                                "data": {"status": "running"}
                            })
                        elif msg_type == "stop":
                            scout.stop()
                            break

                    except asyncio.TimeoutError:
                        continue
                    except WebSocketDisconnect:
                        scout.stop()
                        break
            except Exception as e:
                print(f"[WebSocket] Message listener error: {e}")

        listener_task = asyncio.create_task(listen_for_messages())

        try:
            result = await discovery_task
        finally:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        async with AsyncSessionLocal() as db:
            proj_result = await db.execute(select(Project).where(Project.id == project_id))
            project = proj_result.scalar_one()
            project.status = "completed" if result.get("success") else "failed"
            project.discovery_completed_at = datetime.utcnow()
            project.pages_discovered = result.get("pages_discovered", 0)
            project.features_found = result.get("features_found", 0)
            project.patterns_detected = result.get("patterns_detected", 0)
            await db.commit()

        await websocket.send_json({
            "type": "complete",
            "data": result
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass


# =============================================================================
# Test Case Endpoints
# =============================================================================

class TestCaseCreate(BaseModel):
    page_id: UUID | None = None
    name: str
    instruction: str
    test_type: str = "positive"


class TestCaseFromScenario(BaseModel):
    page_id: UUID
    scenario: str
    test_type: str = "positive"


class TestCaseResponse(BaseModel):
    id: UUID
    project_id: UUID
    page_id: UUID | None
    name: str
    description: str | None
    instruction: str
    steps: list | None
    test_type: str
    source: str
    status: str
    last_run_at: datetime | None
    last_run_status: str | None
    last_run_duration: int | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/{project_id}/tests", response_model=list[TestCaseResponse])
async def get_project_tests(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all test cases for a project."""
    service = TestCaseService(db)
    tests = await service.get_tests_for_project(project_id)
    return tests


@router.get("/{project_id}/pages/{page_id}/tests", response_model=list[TestCaseResponse])
async def get_page_tests(
    project_id: UUID,
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all test cases for a specific page."""
    service = TestCaseService(db)
    tests = await service.get_tests_for_page(page_id)
    return tests


@router.post("/{project_id}/tests", response_model=TestCaseResponse)
async def create_custom_test(
    project_id: UUID,
    data: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom test case."""
    service = TestCaseService(db)
    test_case = await service.create_custom_test(
        project_id=project_id,
        name=data.name,
        instruction=data.instruction,
        page_id=data.page_id,
        test_type=data.test_type,
    )
    return test_case


@router.post("/{project_id}/tests/from-scenario", response_model=TestCaseResponse)
async def create_test_from_scenario(
    project_id: UUID,
    data: TestCaseFromScenario,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a test case from a suggested scenario with optional variant generation."""
    service = TestCaseService(db)
    test_case = await service.create_test_from_scenario(
        project_id=project_id,
        page_id=data.page_id,
        scenario=data.scenario,
        test_type=data.test_type,
    )
    return test_case


@router.post("/{project_id}/pages/{page_id}/tests/generate-all", response_model=list[TestCaseResponse])
async def generate_all_tests_for_page(
    project_id: UUID,
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate test cases for all suggested scenarios on a page."""
    service = TestCaseService(db)
    test_cases = await service.create_all_tests_for_page(
        project_id=project_id,
        page_id=page_id,
    )
    return test_cases


@router.post("/{project_id}/tests/generate-all", response_model=list[TestCaseResponse])
async def generate_all_tests_for_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate test cases for all pages in a project."""
    service = TestCaseService(db)
    test_cases = await service.create_all_tests_for_project(project_id)
    return test_cases


@router.delete("/{project_id}/tests/{test_id}")
async def delete_test(
    project_id: UUID,
    test_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a test case."""
    service = TestCaseService(db)
    success = await service.delete_test(test_id)
    if not success:
        raise HTTPException(status_code=404, detail="Test case not found")
    return {"success": True}


class GenerateVariantsRequest(BaseModel):
    variant_types: list[str] | None = None


class VariantResponse(BaseModel):
    name: str
    type: str
    description: str | None = None
    steps: list[dict]
    expected_result: str | None = None


class GenerateVariantsResponse(BaseModel):
    test_id: UUID
    test_name: str
    variants: list[VariantResponse]


@router.post("/{project_id}/tests/{test_id}/generate-variants")
async def generate_test_variants(
    project_id: UUID,
    test_id: UUID,
    request: GenerateVariantsRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate test variants from recorded steps using LLM analysis.

    Smart features:
    - Detects setup (login) vs test portions - only generates variants for test portion
    - Deduplicates - won't regenerate variants for identical step patterns
    """
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_id,
            TestCase.project_id == project_id
        )
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(status_code=404, detail="Test case not found")

    if not test_case.steps:
        raise HTTPException(status_code=400, detail="No steps found to generate variants from")

    # Generate variants using LLM
    generator = VariantGenerator()
    variant_types = request.variant_types if request else None

    gen_result = await generator.generate_variants(
        steps=test_case.steps,
        variant_types=variant_types,
        test_name=test_case.name,
        test_description=test_case.description or "",
        project_id=str(project_id),  # For deduplication scoping
    )

    return {
        "test_id": str(test_case.id),
        "test_name": test_case.name,
        "variants": [VariantResponse(**v) for v in gen_result.get("variants", [])],
        "setup_boundary": gen_result.get("setup_boundary", 0),
        "setup_type": gen_result.get("setup_type", "none"),
        "setup_variants_skipped": gen_result.get("setup_variants_skipped", False),
        "duplicate_skipped": gen_result.get("duplicate_skipped", False),
    }
