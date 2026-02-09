"""Service for managing test cases - creation, execution, and storage."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_case import TestCase, TestRun
from app.models.project import Project, DiscoveredPage


class TestCaseService:
    """Service for test case management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_test_from_scenario(
        self,
        project_id: uuid.UUID,
        page_id: uuid.UUID,
        scenario: str,
        test_type: str = "positive",
    ) -> TestCase:
        """Create a test case from a suggested scenario."""
        page = await self.db.get(DiscoveredPage, page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        project = await self.db.get(Project, project_id)
        instruction = await self._build_instruction(page, scenario, project)

        test_case = TestCase(
            id=uuid.uuid4(),
            project_id=project_id,
            page_id=page_id,
            name=scenario[:100],  # Truncate for name
            description=scenario,
            instruction=instruction,
            test_type=test_type,
            source="suggested",
            status="pending",
        )

        self.db.add(test_case)
        await self.db.commit()
        await self.db.refresh(test_case)

        return test_case

    async def create_custom_test(
        self,
        project_id: uuid.UUID,
        name: str,
        instruction: str,
        page_id: Optional[uuid.UUID] = None,
        test_type: str = "positive",
    ) -> TestCase:
        """Create a custom test case from user-provided instruction."""
        test_case = TestCase(
            id=uuid.uuid4(),
            project_id=project_id,
            page_id=page_id,
            name=name,
            description=instruction,
            instruction=instruction,
            test_type=test_type,
            source="custom",
            status="pending",
        )

        self.db.add(test_case)
        await self.db.commit()
        await self.db.refresh(test_case)

        return test_case

    async def create_all_tests_for_page(
        self,
        project_id: uuid.UUID,
        page_id: uuid.UUID,
    ) -> list[TestCase]:
        """Create test cases for all suggested scenarios on a page."""
        page = await self.db.get(DiscoveredPage, page_id)
        if not page:
            raise ValueError(f"Page {page_id} not found")

        scenarios = page.test_scenarios or []
        if not scenarios:
            return []

        test_cases = []
        for scenario in scenarios:
            test_case = await self.create_test_from_scenario(
                project_id=project_id,
                page_id=page_id,
                scenario=scenario,
            )
            test_cases.append(test_case)

        return test_cases

    async def create_all_tests_for_project(
        self,
        project_id: uuid.UUID,
    ) -> list[TestCase]:
        """Create test cases for all pages in a project."""
        result = await self.db.execute(
            select(DiscoveredPage)
            .where(DiscoveredPage.project_id == project_id)
            .where(DiscoveredPage.test_scenarios.isnot(None))
        )
        pages = result.scalars().all()

        all_test_cases = []
        for page in pages:
            test_cases = await self.create_all_tests_for_page(
                project_id=project_id,
                page_id=page.id,
            )
            all_test_cases.extend(test_cases)

        return all_test_cases

    async def get_tests_for_project(
        self,
        project_id: uuid.UUID,
    ) -> list[TestCase]:
        """Get all test cases for a project."""
        result = await self.db.execute(
            select(TestCase)
            .where(TestCase.project_id == project_id)
            .order_by(TestCase.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_tests_for_page(
        self,
        page_id: uuid.UUID,
    ) -> list[TestCase]:
        """Get all test cases for a specific page."""
        result = await self.db.execute(
            select(TestCase)
            .where(TestCase.page_id == page_id)
            .order_by(TestCase.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_test_steps(
        self,
        test_case_id: uuid.UUID,
        steps: list[dict],
    ) -> TestCase:
        """Update test case with recorded steps."""
        test_case = await self.db.get(TestCase, test_case_id)
        if not test_case:
            raise ValueError(f"TestCase {test_case_id} not found")

        test_case.steps = steps
        test_case.status = "ready"
        test_case.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(test_case)

        return test_case

    async def update_test_result(
        self,
        test_case_id: uuid.UUID,
        status: str,
        duration: int = None,
        error: str = None,
    ) -> TestCase:
        """Update test case with run result."""
        test_case = await self.db.get(TestCase, test_case_id)
        if not test_case:
            raise ValueError(f"TestCase {test_case_id} not found")

        test_case.last_run_at = datetime.utcnow()
        test_case.last_run_status = status
        test_case.last_run_duration = duration
        test_case.last_run_error = error
        test_case.status = "passing" if status == "passed" else "failing"
        test_case.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(test_case)

        return test_case

    async def delete_test(self, test_case_id: uuid.UUID) -> bool:
        """Delete a test case."""
        test_case = await self.db.get(TestCase, test_case_id)
        if not test_case:
            return False

        await self.db.delete(test_case)
        await self.db.commit()
        return True

    async def _build_instruction(self, page: DiscoveredPage, scenario: str, project: Project = None) -> str:
        """Build an NLP instruction with rich page context."""
        parts = []

        # Header
        parts.append(f"# Test: {scenario}")
        parts.append("")

        # Target page info
        parts.append(f"## Target Page")
        parts.append(f"- Title: {page.title or 'Unknown'}")
        parts.append(f"- URL: {page.url}")
        parts.append(f"- Type: {page.page_type or 'page'}")
        parts.append("")

        # Credentials if page requires auth
        if page.requires_auth and project and project.credentials:
            creds = project.credentials
            parts.append("## Login Credentials (use if login is required)")
            if creds.get("email"):
                parts.append(f"- Email: {creds['email']}")
            if creds.get("username"):
                parts.append(f"- Username: {creds['username']}")
            if creds.get("password"):
                parts.append(f"- Password: {creds['password']}")
            parts.append("")

        # Navigation steps to reach the page
        if page.nav_steps:
            parts.append("## Navigation (how to reach this page from login)")
            for i, step in enumerate(page.nav_steps, 1):
                step_type = step.get("type", "action")
                if step_type == "click":
                    parts.append(f"{i}. Click on '{step.get('text', step.get('selector', 'element'))}'")
                elif step_type == "fill":
                    parts.append(f"{i}. Fill '{step.get('selector', 'field')}' with appropriate value")
                elif step_type == "navigate":
                    parts.append(f"{i}. Navigate to {step.get('value', step.get('url', 'page'))}")
            parts.append("")

        # Form details from LLM analysis
        llm = page.llm_analysis or {}
        forms = llm.get("forms", []) or page.forms_found or []
        if forms:
            parts.append("## Forms on this page")
            for form in forms:
                form_name = form.get("form_purpose") or form.get("form_name") or "Form"
                parts.append(f"### {form_name}")
                fields = form.get("fields", [])
                if fields:
                    parts.append("Fields:")
                    for field in fields:
                        field_name = field.get("label") or field.get("name") or "field"
                        field_type = field.get("field_type") or field.get("type") or "text"
                        required = " (required)" if field.get("required") else ""
                        placeholder = f" - placeholder: '{field.get('placeholder')}'" if field.get("placeholder") else ""
                        parts.append(f"  - {field_name}: {field_type}{required}{placeholder}")
                submit = form.get("submit_button_text")
                if submit:
                    parts.append(f"Submit button: '{submit}'")
            parts.append("")

        # Actions available
        actions = llm.get("actions", []) or page.actions_found or []
        if actions:
            parts.append("## Available Actions")
            for action in actions:
                action_text = action.get("action_text") or action.get("text") or "Action"
                action_type = action.get("action_type") or action.get("type") or ""
                destructive = " (DESTRUCTIVE)" if action.get("is_destructive") else ""
                parts.append(f"- {action_text}{' (' + action_type + ')' if action_type else ''}{destructive}")
            parts.append("")

        # The actual test instruction
        parts.append("## Test Instructions")
        parts.append(scenario)
        parts.append("")
        parts.append("## Expected Behavior")
        parts.append("After completing the test, verify the expected outcome is achieved.")
        parts.append("Report success or failure based on visible results on the page.")

        return "\n".join(parts)
