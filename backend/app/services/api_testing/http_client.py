"""Async HTTP client wrapper with timing and response capture."""

import time
import json
from typing import Any
from dataclasses import dataclass, field

import httpx


@dataclass
class TimingBreakdown:
    """Detailed timing breakdown for HTTP request."""
    dns_ms: int | None = None
    connect_ms: int | None = None
    tls_ms: int | None = None
    ttfb_ms: int | None = None  # Time to first byte
    download_ms: int | None = None


@dataclass
class HTTPResponse:
    """Captured HTTP response with timing information."""
    status_code: int
    headers: dict[str, str]
    body: str
    body_bytes: bytes
    elapsed_ms: int
    timing_breakdown: TimingBreakdown | None = None
    size_bytes: int = 0
    error: str | None = None

    def json(self) -> Any:
        """Parse response body as JSON."""
        return json.loads(self.body)

    def is_json(self) -> bool:
        """Check if response has JSON content type."""
        content_type = self.headers.get("content-type", "")
        return "application/json" in content_type.lower()


class APIHttpClient:
    """Async HTTP client for API testing with timing capture."""

    def __init__(
        self,
        timeout: float = 30.0,
        follow_redirects: bool = True,
        verify_ssl: bool = True,
        max_body_size: int = 10 * 1024 * 1024,  # 10MB max response body
    ):
        self.timeout = timeout
        self.follow_redirects = follow_redirects
        self.verify_ssl = verify_ssl
        self.max_body_size = max_body_size
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=self.follow_redirects,
                verify=self.verify_ssl,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        body: Any = None,
        body_type: str = "json",  # json, form, raw
        timeout: float | None = None,
    ) -> HTTPResponse:
        """
        Execute an HTTP request and return response with timing.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE, etc.)
            url: Full URL to request
            headers: Request headers
            params: Query parameters
            body: Request body content
            body_type: Type of body content (json, form, raw)
            timeout: Request timeout in seconds (overrides default)

        Returns:
            HTTPResponse with status, headers, body, and timing
        """
        client = await self._get_client()

        # Prepare request kwargs
        kwargs: dict[str, Any] = {
            "method": method.upper(),
            "url": url,
            "headers": headers or {},
        }

        if params:
            kwargs["params"] = params

        # Handle body based on type
        if body is not None:
            if body_type == "json":
                kwargs["json"] = body
            elif body_type == "form":
                kwargs["data"] = body
            else:  # raw
                kwargs["content"] = body if isinstance(body, bytes) else str(body).encode()

        if timeout:
            kwargs["timeout"] = timeout

        # Execute request with timing
        start_time = time.perf_counter()

        try:
            response = await client.request(**kwargs)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # Read response body (with size limit)
            body_bytes = await response.aread()
            if len(body_bytes) > self.max_body_size:
                body_bytes = body_bytes[:self.max_body_size]

            # Try to decode as text
            try:
                body_text = body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                body_text = body_bytes.decode("latin-1")

            # Convert headers to dict
            headers_dict = dict(response.headers)

            # Build timing breakdown from httpx extensions if available
            timing = self._extract_timing(response)

            return HTTPResponse(
                status_code=response.status_code,
                headers=headers_dict,
                body=body_text,
                body_bytes=body_bytes,
                elapsed_ms=elapsed_ms,
                timing_breakdown=timing,
                size_bytes=len(body_bytes),
            )

        except httpx.TimeoutException as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return HTTPResponse(
                status_code=0,
                headers={},
                body="",
                body_bytes=b"",
                elapsed_ms=elapsed_ms,
                error=f"Timeout: {str(e)}",
            )
        except httpx.ConnectError as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return HTTPResponse(
                status_code=0,
                headers={},
                body="",
                body_bytes=b"",
                elapsed_ms=elapsed_ms,
                error=f"Connection error: {str(e)}",
            )
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return HTTPResponse(
                status_code=0,
                headers={},
                body="",
                body_bytes=b"",
                elapsed_ms=elapsed_ms,
                error=f"Request error: {str(e)}",
            )

    def _extract_timing(self, response: httpx.Response) -> TimingBreakdown | None:
        """Extract timing breakdown from httpx response extensions."""
        # httpx provides timing info in extensions if available
        try:
            ext = response.extensions
            if not ext:
                return None

            # Try to get network stream timing
            # Note: Not all transports provide this
            return TimingBreakdown()  # Placeholder, actual timing depends on transport
        except Exception:
            return None

    async def get(self, url: str, **kwargs) -> HTTPResponse:
        """Convenience method for GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> HTTPResponse:
        """Convenience method for POST request."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> HTTPResponse:
        """Convenience method for PUT request."""
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs) -> HTTPResponse:
        """Convenience method for PATCH request."""
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> HTTPResponse:
        """Convenience method for DELETE request."""
        return await self.request("DELETE", url, **kwargs)
