"""Main API test execution engine."""

import asyncio
from datetime import datetime
from typing import Callable, Awaitable, Any
from uuid import UUID

from app.services.api_testing.http_client import APIHttpClient, HTTPResponse
from app.services.api_testing.variable_resolver import VariableResolver
from app.services.api_testing.assertion_engine import AssertionEngine, extract_variable


class ExecutionResult:
    """Result of executing a single API request."""

    def __init__(
        self,
        request_id: UUID,
        status: str,
        response: HTTPResponse | None = None,
        resolved_url: str | None = None,
        resolved_headers: dict | None = None,
        resolved_body: str | None = None,
        assertion_results: list[dict] | None = None,
        extracted_variables: dict | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ):
        self.request_id = request_id
        self.status = status  # passed, failed, skipped, error
        self.response = response
        self.resolved_url = resolved_url
        self.resolved_headers = resolved_headers
        self.resolved_body = resolved_body
        self.assertion_results = assertion_results or []
        self.extracted_variables = extracted_variables or {}
        self.error_message = error_message
        self.error_type = error_type
        self.started_at = started_at
        self.finished_at = finished_at

    @property
    def duration_ms(self) -> int | None:
        if self.response:
            return self.response.elapsed_ms
        if self.started_at and self.finished_at:
            return int((self.finished_at - self.started_at).total_seconds() * 1000)
        return None

    @property
    def all_assertions_passed(self) -> bool:
        return all(r.get("passed", False) for r in self.assertion_results)


class CollectionResult:
    """Result of executing an API collection."""

    def __init__(self):
        self.results: list[ExecutionResult] = []
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")

    @property
    def errored(self) -> int:
        return sum(1 for r in self.results if r.status == "error")

    @property
    def all_passed(self) -> bool:
        return all(r.status == "passed" for r in self.results)

    @property
    def total_assertions(self) -> int:
        return sum(len(r.assertion_results) for r in self.results)

    @property
    def passed_assertions(self) -> int:
        return sum(
            sum(1 for a in r.assertion_results if a.get("passed", False))
            for r in self.results
        )

    @property
    def failed_assertions(self) -> int:
        return self.total_assertions - self.passed_assertions

    @property
    def duration_ms(self) -> int | None:
        if self.started_at and self.finished_at:
            return int((self.finished_at - self.started_at).total_seconds() * 1000)
        return None

    @property
    def summary(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errored": self.errored,
            "total_assertions": self.total_assertions,
            "passed_assertions": self.passed_assertions,
            "failed_assertions": self.failed_assertions,
            "duration_ms": self.duration_ms,
            "all_passed": self.all_passed,
        }


class APITestEngine:
    """
    Main execution engine for Python-native API testing.

    Features:
    - Variable resolution and chaining
    - Multiple assertion types
    - Streaming callbacks for real-time updates
    - Collection and single request execution
    """

    def __init__(
        self,
        on_request_start: Callable[[dict], Awaitable[None]] | None = None,
        on_request_complete: Callable[[dict], Awaitable[None]] | None = None,
        on_assertion_result: Callable[[dict], Awaitable[None]] | None = None,
        on_variable_extracted: Callable[[dict], Awaitable[None]] | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the API test engine.

        Args:
            on_request_start: Callback when request execution starts
            on_request_complete: Callback when request execution completes
            on_assertion_result: Callback for each assertion result
            on_variable_extracted: Callback when a variable is extracted
            timeout: Default request timeout in seconds
        """
        self.http_client = APIHttpClient(timeout=timeout)
        self.variable_resolver = VariableResolver()
        self.assertion_engine = AssertionEngine()

        # Callbacks for streaming (WebSocket)
        self.on_request_start = on_request_start
        self.on_request_complete = on_request_complete
        self.on_assertion_result = on_assertion_result
        self.on_variable_extracted = on_variable_extracted

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.close()

    async def execute_collection(
        self,
        requests: list[dict],
        collection_config: dict | None = None,
        environment_config: dict | None = None,
        runtime_variables: dict | None = None,
        request_ids: list[UUID] | None = None,
        stop_on_failure: bool = False,
    ) -> CollectionResult:
        """
        Execute all or selected requests in a collection.

        Args:
            requests: List of request configurations
            collection_config: Collection settings (base_url, auth, variables)
            environment_config: Environment settings (overrides)
            runtime_variables: Variables passed at execution time
            request_ids: Optional list of request IDs to run (None = all)
            stop_on_failure: Stop execution after first failure

        Returns:
            CollectionResult with all execution results
        """
        result = CollectionResult()
        result.started_at = datetime.utcnow()

        # Build initial context
        context = self._build_context(
            collection_config=collection_config,
            environment_config=environment_config,
            runtime_variables=runtime_variables,
        )

        # Filter requests if request_ids provided
        if request_ids:
            request_id_set = set(request_ids)
            requests = [r for r in requests if r.get("id") in request_id_set]

        # Sort by order_index
        requests = sorted(requests, key=lambda r: r.get("order_index", 0))

        # Execute requests sequentially
        for i, request in enumerate(requests):
            try:
                exec_result = await self.execute_single_request(
                    request=request,
                    collection_config=collection_config,
                    environment_config=environment_config,
                    context=context,
                    execution_order=i,
                )

                result.results.append(exec_result)

                # Update context with extracted variables for chaining
                if exec_result.extracted_variables:
                    context.update(exec_result.extracted_variables)

                # Stop on failure if configured
                if stop_on_failure and exec_result.status in ("failed", "error"):
                    # Mark remaining requests as skipped
                    for remaining in requests[i + 1:]:
                        result.results.append(
                            ExecutionResult(
                                request_id=remaining.get("id"),
                                status="skipped",
                                error_message="Skipped due to previous failure",
                            )
                        )
                    break

            except Exception as e:
                result.results.append(
                    ExecutionResult(
                        request_id=request.get("id"),
                        status="error",
                        error_message=str(e),
                        error_type="execution",
                    )
                )
                if stop_on_failure:
                    break

        result.finished_at = datetime.utcnow()
        return result

    async def execute_single_request(
        self,
        request: dict,
        collection_config: dict | None = None,
        environment_config: dict | None = None,
        context: dict | None = None,
        execution_order: int = 0,
    ) -> ExecutionResult:
        """
        Execute a single API request.

        Args:
            request: Request configuration
            collection_config: Collection settings
            environment_config: Environment settings
            context: Existing variable context (for chaining)
            execution_order: Order index in collection execution

        Returns:
            ExecutionResult with response and assertion results
        """
        request_id = request.get("id")
        started_at = datetime.utcnow()

        # Build context if not provided
        if context is None:
            context = self._build_context(
                collection_config=collection_config,
                environment_config=environment_config,
            )

        # Notify start
        if self.on_request_start:
            await self.on_request_start({
                "request_id": str(request_id),
                "name": request.get("name"),
                "method": request.get("method"),
                "url_path": request.get("url_path"),
                "execution_order": execution_order,
            })

        try:
            # Resolve variables in request
            resolved_url = self._build_full_url(request, collection_config, environment_config, context)
            resolved_headers = self._build_headers(request, collection_config, environment_config, context)
            resolved_body, body_type = self._build_body(request, context)

            # Resolve query params
            query_params = None
            if request.get("query_params"):
                query_params = self.variable_resolver.resolve_dict(request["query_params"], context)

            # Get timeout
            timeout = request.get("timeout_ms")
            if timeout:
                timeout = timeout / 1000.0  # Convert to seconds

            # Execute HTTP request
            response = await self.http_client.request(
                method=request.get("method", "GET"),
                url=resolved_url,
                headers=resolved_headers,
                params=query_params,
                body=resolved_body,
                body_type=body_type,
                timeout=timeout,
            )

            # Check for connection/timeout errors
            if response.error:
                return ExecutionResult(
                    request_id=request_id,
                    status="error",
                    response=response,
                    resolved_url=resolved_url,
                    resolved_headers=resolved_headers,
                    resolved_body=str(resolved_body) if resolved_body else None,
                    error_message=response.error,
                    error_type="connection" if "Connection" in response.error else "timeout",
                    started_at=started_at,
                    finished_at=datetime.utcnow(),
                )

            # Run assertions
            assertion_results = await self.assertion_engine.run_all(
                request.get("assertions"),
                response,
                context,
            )

            # Notify assertion results
            if self.on_assertion_result:
                for assertion in assertion_results:
                    await self.on_assertion_result({
                        "request_id": str(request_id),
                        **assertion,
                    })

            # Extract variables for chaining
            extracted_vars = {}
            for extraction in request.get("variable_extractions") or []:
                var_name, var_value = extract_variable(extraction, response)
                if var_name:
                    extracted_vars[var_name] = var_value
                    if self.on_variable_extracted:
                        await self.on_variable_extracted({
                            "request_id": str(request_id),
                            "name": var_name,
                            "value": var_value,
                        })

            # Determine status
            all_passed = all(r.get("passed", False) for r in assertion_results)
            status = "passed" if all_passed else "failed"

            exec_result = ExecutionResult(
                request_id=request_id,
                status=status,
                response=response,
                resolved_url=resolved_url,
                resolved_headers=resolved_headers,
                resolved_body=str(resolved_body) if resolved_body else None,
                assertion_results=assertion_results,
                extracted_variables=extracted_vars,
                started_at=started_at,
                finished_at=datetime.utcnow(),
            )

            # Notify completion
            if self.on_request_complete:
                await self.on_request_complete({
                    "request_id": str(request_id),
                    "status": status,
                    "response_status": response.status_code,
                    "duration_ms": response.elapsed_ms,
                    "assertions_passed": sum(1 for r in assertion_results if r.get("passed")),
                    "assertions_total": len(assertion_results),
                })

            return exec_result

        except Exception as e:
            exec_result = ExecutionResult(
                request_id=request_id,
                status="error",
                error_message=str(e),
                error_type="execution",
                started_at=started_at,
                finished_at=datetime.utcnow(),
            )

            if self.on_request_complete:
                await self.on_request_complete({
                    "request_id": str(request_id),
                    "status": "error",
                    "error": str(e),
                })

            return exec_result

    def _build_context(
        self,
        collection_config: dict | None = None,
        environment_config: dict | None = None,
        runtime_variables: dict | None = None,
    ) -> dict:
        """Build execution context from various sources."""
        return self.variable_resolver.build_context(
            environment_vars=environment_config.get("variables") if environment_config else None,
            collection_vars=collection_config.get("variables") if collection_config else None,
            runtime_vars=runtime_variables,
        )

    def _build_full_url(
        self,
        request: dict,
        collection_config: dict | None,
        environment_config: dict | None,
        context: dict,
    ) -> str:
        """Build full URL from base URL and path."""
        url_path = request.get("url_path", "")

        # Resolve variables in URL path
        url_path = self.variable_resolver.resolve(url_path, context)

        # If URL is already absolute, return it
        if url_path.startswith(("http://", "https://")):
            return url_path

        # Get base URL (environment overrides collection)
        base_url = ""
        if environment_config and environment_config.get("base_url"):
            base_url = environment_config["base_url"]
        elif collection_config and collection_config.get("base_url"):
            base_url = collection_config["base_url"]

        # Resolve variables in base URL
        base_url = self.variable_resolver.resolve(base_url, context)

        # Combine base URL and path
        if base_url:
            base_url = base_url.rstrip("/")
            url_path = url_path.lstrip("/")
            return f"{base_url}/{url_path}"

        return url_path

    def _build_headers(
        self,
        request: dict,
        collection_config: dict | None,
        environment_config: dict | None,
        context: dict,
    ) -> dict:
        """Build headers from collection, environment, and request."""
        headers = {}

        # Start with collection default headers
        if collection_config and collection_config.get("default_headers"):
            headers.update(collection_config["default_headers"])

        # Override with environment headers
        if environment_config and environment_config.get("default_headers"):
            headers.update(environment_config["default_headers"])

        # Override with request headers
        if request.get("headers"):
            headers.update(request["headers"])

        # Add auth headers
        auth_config = None
        if environment_config and environment_config.get("auth_config"):
            auth_config = environment_config["auth_config"]
        elif collection_config and collection_config.get("auth_config"):
            auth_config = collection_config["auth_config"]

        if auth_config:
            auth_headers = self._build_auth_headers(auth_config, context)
            headers.update(auth_headers)

        # Resolve variables in headers
        headers = self.variable_resolver.resolve_dict(headers, context)

        return headers

    def _build_auth_headers(self, auth_config: dict, context: dict) -> dict:
        """Build authentication headers from auth config."""
        auth_type = auth_config.get("type", "none")
        config = auth_config.get("config", {})

        if auth_type == "bearer":
            token = self.variable_resolver.resolve(config.get("token", ""), context)
            return {"Authorization": f"Bearer {token}"}

        elif auth_type == "basic":
            import base64
            username = self.variable_resolver.resolve(config.get("username", ""), context)
            password = self.variable_resolver.resolve(config.get("password", ""), context)
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {credentials}"}

        elif auth_type == "api_key":
            key = config.get("key", "")
            value = self.variable_resolver.resolve(config.get("value", ""), context)
            location = config.get("in", "header")
            if location == "header":
                return {key: value}
            # Query param auth handled elsewhere

        return {}

    def _build_body(self, request: dict, context: dict) -> tuple[Any, str]:
        """Build request body from configuration."""
        body_config = request.get("body")
        if not body_config:
            return None, "none"

        body_type = body_config.get("type", "none")
        content = body_config.get("content")

        if body_type == "none" or content is None:
            return None, "none"

        if body_type == "json":
            # Resolve variables in JSON content
            resolved = self.variable_resolver.resolve_any(content, context)
            return resolved, "json"

        elif body_type == "form":
            # Resolve variables in form data
            resolved = self.variable_resolver.resolve_dict(content, context)
            return resolved, "form"

        elif body_type == "raw":
            # Resolve variables in raw content
            resolved = self.variable_resolver.resolve(str(content), context)
            return resolved, "raw"

        elif body_type == "graphql":
            # GraphQL has query and variables
            query = self.variable_resolver.resolve(content.get("query", ""), context)
            variables = self.variable_resolver.resolve_dict(content.get("variables", {}), context)
            return {"query": query, "variables": variables}, "json"

        return content, "raw"
