"""AI-powered API test generation using LLM."""

import json
import uuid
from typing import Any

from app.services.llm_providers import get_llm_provider
from app.config import get_settings


class APITestGenerator:
    """
    Generate API tests using LLM.

    Features:
    - Generate tests from natural language descriptions
    - Suggest assertions based on sample responses
    - Generate comprehensive tests from OpenAPI specs
    """

    SYSTEM_PROMPT = """You are an API testing expert. Generate comprehensive API test definitions.

Output ONLY valid JSON. No markdown, no explanation, just the JSON array.

For each test request, include:
{
    "name": "descriptive name",
    "method": "GET|POST|PUT|DELETE|PATCH",
    "url_path": "/api/endpoint",
    "headers": {"key": "value"},
    "body": {"type": "json", "content": {...}},
    "assertions": [
        {"type": "status", "config": {"expected": 200}},
        {"type": "jsonpath", "config": {"path": "$.data", "operator": "exists"}}
    ],
    "description": "What this test verifies"
}

Generate both positive tests (expected success) and negative tests (expected failures, edge cases).
Use {{variable}} syntax for dynamic values."""

    def __init__(self, provider: str | None = None):
        """Initialize with specified or default LLM provider."""
        self.llm = get_llm_provider(provider)

    async def from_natural_language(
        self,
        prompt: str,
        base_url: str | None = None,
        existing_variables: list[str] | None = None,
        max_tests: int = 5,
    ) -> list[dict]:
        """
        Generate API tests from natural language description.

        Args:
            prompt: Natural language description of what to test
            base_url: Optional base URL for context
            existing_variables: List of available variable names
            max_tests: Maximum number of tests to generate

        Returns:
            List of APIRequest-compatible dicts
        """
        context = ""
        if base_url:
            context += f"\nBase URL: {base_url}"
        if existing_variables:
            context += f"\nAvailable variables: {', '.join(existing_variables)}"

        full_prompt = f"""Generate API tests for the following requirement:

{prompt}
{context}

Generate up to {max_tests} test cases. Include positive and negative test scenarios.
Output ONLY a JSON array of test objects."""

        response = await self.llm.ainvoke(full_prompt)
        return self._parse_response(response.content)

    async def suggest_assertions(
        self,
        method: str,
        url_path: str,
        sample_response: dict | None = None,
        response_status: int | None = None,
    ) -> list[dict]:
        """
        Suggest assertions based on request and sample response.

        Args:
            method: HTTP method
            url_path: Request URL path
            sample_response: Sample response body (if available)
            response_status: Sample response status code

        Returns:
            List of assertion configurations
        """
        prompt = f"""Suggest comprehensive assertions for this API request:

Method: {method}
URL: {url_path}
"""

        if response_status:
            prompt += f"Sample Status: {response_status}\n"

        if sample_response:
            # Truncate large responses
            response_str = json.dumps(sample_response, indent=2)
            if len(response_str) > 2000:
                response_str = response_str[:2000] + "\n... (truncated)"
            prompt += f"Sample Response:\n{response_str}\n"

        prompt += """
Generate assertions that:
1. Verify response status code
2. Validate response structure (JSONPath for key fields)
3. Check critical fields exist and have correct types
4. Verify timing if appropriate

Output ONLY a JSON array of assertion objects with format:
[{"type": "status|jsonpath|header|timing", "name": "description", "config": {...}}]"""

        response = await self.llm.ainvoke(prompt)
        return self._parse_response(response.content)

    async def improve_test(
        self,
        test: dict,
        improvement_type: str = "comprehensive",
    ) -> dict:
        """
        Improve an existing test with additional assertions or variations.

        Args:
            test: Existing test configuration
            improvement_type: Type of improvement (comprehensive, security, performance)

        Returns:
            Improved test configuration
        """
        test_str = json.dumps(test, indent=2)

        prompt = f"""Improve this API test to be more {improvement_type}:

{test_str}

Add missing assertions, edge case handling, and improve coverage.
Output ONLY the improved test as a single JSON object."""

        response = await self.llm.ainvoke(prompt)
        results = self._parse_response(response.content)
        return results[0] if results else test

    async def generate_negative_tests(
        self,
        positive_test: dict,
        max_tests: int = 3,
    ) -> list[dict]:
        """
        Generate negative test cases from a positive test.

        Args:
            positive_test: Working positive test case
            max_tests: Maximum negative tests to generate

        Returns:
            List of negative test cases
        """
        test_str = json.dumps(positive_test, indent=2)

        prompt = f"""Generate negative test cases for this API test:

{test_str}

Create up to {max_tests} negative tests that verify:
- Invalid input handling (wrong types, missing required fields)
- Boundary conditions (empty values, very long strings, special characters)
- Authentication/authorization failures
- Resource not found scenarios

Each test should expect an appropriate error response.
Output ONLY a JSON array of test objects."""

        response = await self.llm.ainvoke(prompt)
        return self._parse_response(response.content)

    def _parse_response(self, content: str) -> list[dict]:
        """Parse LLM response to extract JSON."""
        content = content.strip()

        # Try to find JSON array in response
        start_idx = content.find("[")
        end_idx = content.rfind("]")

        if start_idx != -1 and end_idx != -1:
            json_str = content[start_idx:end_idx + 1]
            try:
                result = json.loads(json_str)
                if isinstance(result, list):
                    return self._normalize_tests(result)
            except json.JSONDecodeError:
                pass

        # Try to find single JSON object
        start_idx = content.find("{")
        end_idx = content.rfind("}")

        if start_idx != -1 and end_idx != -1:
            json_str = content[start_idx:end_idx + 1]
            try:
                result = json.loads(json_str)
                if isinstance(result, dict):
                    return self._normalize_tests([result])
            except json.JSONDecodeError:
                pass

        return []

    def _normalize_tests(self, tests: list[dict]) -> list[dict]:
        """Normalize test objects to ensure consistent structure."""
        normalized = []

        for test in tests:
            # Ensure required fields
            if not test.get("name"):
                continue

            # Add ID
            test["id"] = str(uuid.uuid4())

            # Normalize method
            test["method"] = test.get("method", "GET").upper()

            # Ensure url_path
            if not test.get("url_path"):
                test["url_path"] = "/"

            # Normalize body
            body = test.get("body")
            if body and not isinstance(body, dict):
                test["body"] = {"type": "raw", "content": str(body)}
            elif body and "type" not in body:
                test["body"] = {"type": "json", "content": body}

            # Ensure assertions is a list
            if not isinstance(test.get("assertions"), list):
                test["assertions"] = []

            # Ensure headers is a dict
            if not isinstance(test.get("headers"), dict):
                test["headers"] = {}

            normalized.append(test)

        return normalized
