"""Assertion engine for API test assertions."""

import re
import json
from typing import Any

import jsonschema
from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.exceptions import JsonPathParserError

from app.services.api_testing.http_client import HTTPResponse


class AssertionEngine:
    """
    Executes assertions against API responses.

    Supported assertion types:
    - status: Response status code validation
    - jsonpath: JSONPath extraction and comparison
    - header: Response header validation
    - timing: Response time threshold
    - schema: JSON Schema validation
    - body_contains: Substring presence in body
    - body_equals: Exact body match
    """

    async def run_all(
        self,
        assertions: list[dict] | None,
        response: HTTPResponse,
        context: dict,
    ) -> list[dict]:
        """
        Run all assertions and return results.

        Args:
            assertions: List of assertion configurations
            response: HTTP response to validate
            context: Variable context for dynamic values

        Returns:
            List of assertion result dictionaries
        """
        results = []
        for assertion in assertions or []:
            result = await self.run_one(assertion, response, context)
            results.append(result)
        return results

    async def run_one(
        self,
        assertion: dict,
        response: HTTPResponse,
        context: dict,
    ) -> dict:
        """
        Execute a single assertion.

        Args:
            assertion: Assertion configuration {type, name, config}
            response: HTTP response to validate
            context: Variable context for dynamic values

        Returns:
            Assertion result dictionary
        """
        assertion_type = assertion.get("type")
        config = assertion.get("config", {})
        name = assertion.get("name")

        handlers = {
            "status": self._assert_status,
            "jsonpath": self._assert_jsonpath,
            "header": self._assert_header,
            "timing": self._assert_timing,
            "schema": self._assert_schema,
            "body_contains": self._assert_body_contains,
            "body_equals": self._assert_body_equals,
        }

        handler = handlers.get(assertion_type)
        if not handler:
            return {
                "type": assertion_type,
                "name": name,
                "passed": False,
                "message": f"Unknown assertion type: {assertion_type}",
            }

        try:
            result = await handler(config, response, context)
            result["name"] = name
            return result
        except Exception as e:
            return {
                "type": assertion_type,
                "name": name,
                "passed": False,
                "message": f"Assertion error: {str(e)}",
            }

    async def _assert_status(
        self,
        config: dict,
        response: HTTPResponse,
        context: dict,
    ) -> dict:
        """Assert response status code."""
        expected = config.get("expected")
        operator = config.get("operator", "equals")
        actual = response.status_code

        if operator == "equals":
            passed = actual == expected
        elif operator == "in":
            passed = actual in (expected if isinstance(expected, list) else [expected])
        elif operator == "range":
            # expected should be [min, max]
            if isinstance(expected, list) and len(expected) == 2:
                passed = expected[0] <= actual <= expected[1]
            else:
                passed = False
        else:
            passed = actual == expected

        return {
            "type": "status",
            "passed": passed,
            "expected": expected,
            "actual": actual,
            "message": f"Status {actual} {'==' if passed else '!='} {expected}",
        }

    async def _assert_jsonpath(
        self,
        config: dict,
        response: HTTPResponse,
        context: dict,
    ) -> dict:
        """Assert value at JSONPath matches expected."""
        path = config.get("path")
        expected = config.get("expected")
        operator = config.get("operator", "equals")

        try:
            body = response.json()
        except json.JSONDecodeError:
            return {
                "type": "jsonpath",
                "passed": False,
                "message": "Response is not valid JSON",
            }

        try:
            jsonpath_expr = jsonpath_parse(path)
            matches = [match.value for match in jsonpath_expr.find(body)]
        except JsonPathParserError as e:
            return {
                "type": "jsonpath",
                "passed": False,
                "message": f"Invalid JSONPath: {str(e)}",
            }

        # Get first match or None
        actual = matches[0] if matches else None

        # Apply operator
        if operator == "exists":
            passed = len(matches) > 0
            message = f"Path {path} {'exists' if passed else 'does not exist'}"
        elif operator == "not_exists":
            passed = len(matches) == 0
            message = f"Path {path} {'does not exist' if passed else 'exists'}"
        elif operator == "equals":
            passed = actual == expected
            message = f"{path} = {actual}"
        elif operator == "not_equals":
            passed = actual != expected
            message = f"{path} != {expected} (actual: {actual})"
        elif operator == "contains":
            passed = expected in str(actual) if actual else False
            message = f"{path} contains '{expected}'"
        elif operator == "not_contains":
            passed = expected not in str(actual) if actual else True
            message = f"{path} does not contain '{expected}'"
        elif operator == "greater_than":
            try:
                passed = float(actual) > float(expected)
            except (TypeError, ValueError):
                passed = False
            message = f"{path} > {expected} (actual: {actual})"
        elif operator == "less_than":
            try:
                passed = float(actual) < float(expected)
            except (TypeError, ValueError):
                passed = False
            message = f"{path} < {expected} (actual: {actual})"
        elif operator == "matches":
            # Regex match
            try:
                passed = bool(re.search(expected, str(actual))) if actual else False
            except re.error:
                passed = False
            message = f"{path} matches '{expected}'"
        else:
            passed = actual == expected
            message = f"{path} = {actual}"

        return {
            "type": "jsonpath",
            "path": path,
            "passed": passed,
            "expected": expected,
            "actual": actual,
            "message": message,
        }

    async def _assert_header(
        self,
        config: dict,
        response: HTTPResponse,
        context: dict,
    ) -> dict:
        """Assert response header value."""
        name = config.get("name", "").lower()
        expected = config.get("expected")
        operator = config.get("operator", "exists")

        # Get header value (case-insensitive)
        actual = None
        for key, value in response.headers.items():
            if key.lower() == name:
                actual = value
                break

        if operator == "exists":
            passed = actual is not None
            message = f"Header '{name}' {'exists' if passed else 'does not exist'}"
        elif operator == "not_exists":
            passed = actual is None
            message = f"Header '{name}' {'does not exist' if passed else 'exists'}"
        elif operator == "equals":
            passed = actual == expected
            message = f"Header '{name}' = '{actual}'"
        elif operator == "contains":
            passed = expected in actual if actual else False
            message = f"Header '{name}' contains '{expected}'"
        elif operator == "matches":
            try:
                passed = bool(re.search(expected, actual)) if actual else False
            except re.error:
                passed = False
            message = f"Header '{name}' matches '{expected}'"
        else:
            passed = actual == expected
            message = f"Header '{name}' = '{actual}'"

        return {
            "type": "header",
            "header": name,
            "passed": passed,
            "expected": expected,
            "actual": actual,
            "message": message,
        }

    async def _assert_timing(
        self,
        config: dict,
        response: HTTPResponse,
        context: dict,
    ) -> dict:
        """Assert response time is within threshold."""
        max_ms = config.get("max_ms")
        actual = response.elapsed_ms
        passed = actual <= max_ms

        return {
            "type": "timing",
            "passed": passed,
            "expected": f"<= {max_ms}ms",
            "actual": f"{actual}ms",
            "message": f"Response time {actual}ms {'<=' if passed else '>'} {max_ms}ms",
        }

    async def _assert_schema(
        self,
        config: dict,
        response: HTTPResponse,
        context: dict,
    ) -> dict:
        """Validate response body against JSON Schema."""
        schema = config.get("schema")

        try:
            body = response.json()
        except json.JSONDecodeError:
            return {
                "type": "schema",
                "passed": False,
                "message": "Response is not valid JSON",
            }

        try:
            jsonschema.validate(body, schema)
            return {
                "type": "schema",
                "passed": True,
                "message": "Response matches schema",
            }
        except jsonschema.ValidationError as e:
            return {
                "type": "schema",
                "passed": False,
                "message": f"Schema validation failed: {e.message}",
            }
        except jsonschema.SchemaError as e:
            return {
                "type": "schema",
                "passed": False,
                "message": f"Invalid schema: {e.message}",
            }

    async def _assert_body_contains(
        self,
        config: dict,
        response: HTTPResponse,
        context: dict,
    ) -> dict:
        """Assert response body contains substring."""
        expected = config.get("expected", "")
        case_sensitive = config.get("case_sensitive", True)

        body = response.body
        search_body = body if case_sensitive else body.lower()
        search_expected = expected if case_sensitive else expected.lower()

        passed = search_expected in search_body

        return {
            "type": "body_contains",
            "passed": passed,
            "expected": expected,
            "message": f"Body {'contains' if passed else 'does not contain'} '{expected}'",
        }

    async def _assert_body_equals(
        self,
        config: dict,
        response: HTTPResponse,
        context: dict,
    ) -> dict:
        """Assert response body equals expected value."""
        expected = config.get("expected", "")
        ignore_whitespace = config.get("ignore_whitespace", False)

        body = response.body
        compare_body = body.strip() if ignore_whitespace else body
        compare_expected = expected.strip() if ignore_whitespace else expected

        passed = compare_body == compare_expected

        return {
            "type": "body_equals",
            "passed": passed,
            "expected": expected[:100] + "..." if len(expected) > 100 else expected,
            "actual": body[:100] + "..." if len(body) > 100 else body,
            "message": f"Body {'equals' if passed else 'does not equal'} expected",
        }


def extract_variable(
    extraction: dict,
    response: HTTPResponse,
) -> tuple[str, Any]:
    """
    Extract a variable from response based on extraction config.

    Args:
        extraction: {name, source, path, default}
        response: HTTP response to extract from

    Returns:
        Tuple of (variable_name, extracted_value)
    """
    name = extraction.get("name")
    source = extraction.get("source", "jsonpath")
    path = extraction.get("path", "")
    default = extraction.get("default")

    value = default

    try:
        if source == "jsonpath":
            body = response.json()
            jsonpath_expr = jsonpath_parse(path)
            matches = [match.value for match in jsonpath_expr.find(body)]
            if matches:
                value = matches[0]

        elif source == "header":
            # path is the header name
            for key, val in response.headers.items():
                if key.lower() == path.lower():
                    value = val
                    break

        elif source == "body":
            value = response.body

        elif source == "status":
            value = response.status_code

        elif source == "regex":
            # path is the regex pattern with a capture group
            match = re.search(path, response.body)
            if match:
                # Return first capture group if exists, else full match
                value = match.group(1) if match.groups() else match.group(0)

    except Exception:
        # Use default on any extraction error
        pass

    return name, value
