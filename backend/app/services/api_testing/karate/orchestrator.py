"""Karate test orchestrator for managing JVM worker pool via Redis."""

import asyncio
import json
import re
import time
import uuid
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from urllib.parse import urljoin

import redis.asyncio as aioredis

from app.config import get_settings


@dataclass
class KarateJobResult:
    """Result of a Karate job execution."""
    job_id: str
    status: str  # pending, running, complete, error, timeout
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    cucumber_report: list | None = None
    parsed_results: list | None = None
    http_captures: list | None = None  # HTTP request/response captures per scenario
    error: str | None = None


@dataclass
class KarateScenarioResult:
    """Parsed result for a single Karate scenario."""
    name: str
    tags: list[str] = field(default_factory=list)
    status: str = "unknown"  # passed, failed, skipped
    steps: list[dict] = field(default_factory=list)
    duration_ms: int = 0
    error_message: str | None = None
    # HTTP request/response details
    request_url: str | None = None
    request_method: str | None = None
    request_headers: dict | None = None
    request_body: Any = None
    response_status: int | None = None
    response_headers: dict | None = None
    response_body: Any = None
    response_time_ms: int | None = None


class KarateOrchestrator:
    """
    Manages Karate test execution via Redis job queue and worker pool.

    Architecture:
    - Backend submits jobs to Redis queue (karate:jobs)
    - Karate workers poll queue and execute .feature files
    - Workers publish results to Redis (karate:results:{job_id})
    - Backend polls for results

    Job Format:
    {
        "id": "uuid",
        "feature": ".feature file content",
        "config": "karate-config.js content (optional)",
        "env_vars": {"key": "value"},
        "tags": ["@smoke", "@api"],
        "submitted_at": "ISO timestamp",
    }

    Result Format:
    {
        "job_id": "uuid",
        "status": "complete|error",
        "report": [Cucumber JSON],
        "error": "error message if any",
        "finished_at": "ISO timestamp",
    }
    """

    def __init__(self, redis_url: str | None = None):
        """
        Initialize the Karate orchestrator.

        Args:
            redis_url: Redis connection URL. If None, uses settings.
        """
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self._redis: aioredis.Redis | None = None

        # Queue names
        self.job_queue = "karate:jobs"
        self.result_prefix = "karate:results:"
        self.status_prefix = "karate:status:"

    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def submit_feature(
        self,
        feature_content: str,
        config_content: str | None = None,
        env_vars: dict[str, str] | None = None,
        tags: list[str] | None = None,
        additional_files: dict[str, str] | None = None,
    ) -> str:
        """
        Submit a Karate .feature file for execution.

        Args:
            feature_content: The .feature file content (Gherkin syntax)
            config_content: Optional karate-config.js content
            env_vars: Environment variables to pass to Karate
            tags: Tags to filter scenarios (e.g., ["@smoke", "~@skip"])
            additional_files: Additional files needed (e.g., helper functions)

        Returns:
            Job ID for tracking execution
        """
        redis = await self._get_redis()

        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "feature": feature_content,
            "config": config_content,
            "env_vars": env_vars or {},
            "tags": tags or [],
            "additional_files": additional_files or {},
            "submitted_at": datetime.utcnow().isoformat(),
        }

        # Set initial status
        await redis.set(
            f"{self.status_prefix}{job_id}",
            "pending",
            ex=3600,  # 1 hour expiry
        )

        # Push job to queue (workers use BRPOP)
        await redis.lpush(self.job_queue, json.dumps(job))

        return job_id

    async def get_status(self, job_id: str) -> str:
        """
        Get current status of a job.

        Args:
            job_id: Job ID to check

        Returns:
            Status string: pending, running, complete, error
        """
        redis = await self._get_redis()
        status = await redis.get(f"{self.status_prefix}{job_id}")
        return status or "unknown"

    async def get_result(
        self,
        job_id: str,
        timeout_seconds: int = 300,
        poll_interval: float = 0.5,
    ) -> KarateJobResult:
        """
        Wait for and retrieve execution result.

        Args:
            job_id: Job ID to wait for
            timeout_seconds: Maximum time to wait
            poll_interval: Seconds between status checks

        Returns:
            KarateJobResult with execution details

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        redis = await self._get_redis()
        result_key = f"{self.result_prefix}{job_id}"

        start = time.time()
        while time.time() - start < timeout_seconds:
            # Check for result
            result_json = await redis.get(result_key)
            if result_json:
                result_data = json.loads(result_json)

                # Parse Cucumber report if present
                parsed_results = None
                http_captures = result_data.get("http_captures")
                if result_data.get("report"):
                    parsed_results = self.parse_cucumber_report(result_data["report"], http_captures)

                return KarateJobResult(
                    job_id=job_id,
                    status=result_data.get("status", "complete"),
                    started_at=datetime.fromisoformat(result_data["started_at"]) if result_data.get("started_at") else None,
                    finished_at=datetime.fromisoformat(result_data["finished_at"]) if result_data.get("finished_at") else None,
                    duration_ms=result_data.get("duration_ms"),
                    cucumber_report=result_data.get("report"),
                    parsed_results=parsed_results,
                    http_captures=http_captures,
                    error=result_data.get("error"),
                )

            # Check status for early failure detection
            status = await redis.get(f"{self.status_prefix}{job_id}")
            if status == "error":
                return KarateJobResult(
                    job_id=job_id,
                    status="error",
                    error="Job failed before producing results",
                )

            await asyncio.sleep(poll_interval)

        # Timeout reached
        return KarateJobResult(
            job_id=job_id,
            status="timeout",
            error=f"Job did not complete within {timeout_seconds} seconds",
        )

    async def cancel_job(self, job_id: str) -> bool:
        """
        Attempt to cancel a pending job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if job was cancelled, False if already running/complete
        """
        redis = await self._get_redis()

        status = await redis.get(f"{self.status_prefix}{job_id}")
        if status in ("complete", "error", "running"):
            return False

        # Mark as cancelled
        await redis.set(f"{self.status_prefix}{job_id}", "cancelled", ex=3600)

        # Note: Job might already be picked up by worker.
        # Worker should check status before execution.
        return True

    def parse_cucumber_report(self, report_json: list, http_captures: list | None = None) -> list[KarateScenarioResult]:
        """
        Parse Cucumber JSON report into structured results.

        Karate generates Cucumber-compatible JSON reports with this structure:
        [
            {
                "keyword": "Feature",
                "name": "Feature name",
                "elements": [
                    {
                        "keyword": "Scenario",
                        "name": "Scenario name",
                        "tags": [{"name": "@tag"}],
                        "steps": [
                            {
                                "keyword": "Given ",
                                "name": "step text",
                                "result": {
                                    "status": "passed|failed|skipped",
                                    "duration": nanoseconds,
                                    "error_message": "if failed"
                                }
                            }
                        ]
                    }
                ]
            }
        ]

        Args:
            report_json: Cucumber JSON report from Karate
            http_captures: Optional list of HTTP request/response captures

        Returns:
            List of parsed scenario results
        """
        results = []

        # Build a lookup map from scenario name to HTTP capture
        http_capture_map = {}
        if http_captures:
            for capture in http_captures:
                scenario_name = capture.get("scenarioName")
                if scenario_name:
                    http_capture_map[scenario_name] = capture

        for feature in report_json or []:
            for element in feature.get("elements", []):
                if element.get("type") == "scenario":
                    scenario_name = element.get("name", "Unknown Scenario")

                    # Skip the HTTP capture output scenario
                    if scenario_name == "Write HTTP Captures to File":
                        continue

                    # Extract tags
                    tags = [t.get("name", "") for t in element.get("tags", [])]

                    # Parse steps
                    steps = []
                    scenario_passed = True
                    total_duration_ns = 0
                    error_message = None

                    for step in element.get("steps", []):
                        step_result = step.get("result", {})
                        step_status = step_result.get("status", "unknown")
                        step_duration = step_result.get("duration", 0)

                        steps.append({
                            "keyword": step.get("keyword", "").strip(),
                            "name": step.get("name", ""),
                            "status": step_status,
                            "duration_ns": step_duration,
                            "error_message": step_result.get("error_message"),
                        })

                        total_duration_ns += step_duration

                        if step_status != "passed":
                            scenario_passed = False
                            if step_result.get("error_message") and not error_message:
                                error_message = step_result["error_message"]

                    # Get HTTP capture for this scenario
                    http_capture = http_capture_map.get(scenario_name, {})
                    request_data = http_capture.get("request", {})
                    response_data = http_capture.get("response", {})

                    # Extract request details (support both url/urlBase+uri and uri alone)
                    request_url = request_data.get("url") or request_data.get("urlBase")
                    if request_data.get("uri"):
                        request_url = (request_url or "") + str(request_data.get("uri", ""))
                    if not request_url and request_data.get("uri"):
                        request_url = request_data.get("uri")

                    response_status = response_data.get("status")
                    if response_status is not None and not isinstance(response_status, int):
                        try:
                            response_status = int(response_status)
                        except (TypeError, ValueError):
                            response_status = None

                    # Fallback: extract response status from "Then status XXX" steps
                    if response_status is None:
                        for step in steps:
                            step_name = (step.get("name") or "").strip()
                            match = re.search(r"status\s+(\d{3})", step_name, re.IGNORECASE)
                            if match:
                                response_status = int(match.group(1))
                                break

                    results.append(KarateScenarioResult(
                        name=scenario_name,
                        tags=tags,
                        status="passed" if scenario_passed else "failed",
                        steps=steps,
                        duration_ms=int(total_duration_ns / 1_000_000),
                        error_message=error_message,
                        # HTTP request details
                        request_url=request_url,
                        request_method=request_data.get("method"),
                        request_headers=request_data.get("headers"),
                        request_body=request_data.get("body"),
                        # HTTP response details
                        response_status=response_status,
                        response_headers=response_data.get("headers"),
                        response_body=response_data.get("body"),
                        response_time_ms=int(response_data.get("time")) if response_data.get("time") else None,
                    ))

        return results

    def results_to_unified_format(
        self,
        results: list[KarateScenarioResult],
        original_requests: list[dict] | None = None,
        collection_config: dict | None = None,
    ) -> list[dict]:
        """
        Convert Karate results to unified API test result format.

        This allows Karate results to be displayed alongside Python engine results
        in the same dashboard. When HTTP captures are missing, request details are
        filled from original_requests and collection_config so the UI still shows
        payload and method/URL.

        Args:
            results: Parsed Karate scenario results
            original_requests: Optional list of request dicts (method, url_path, headers, body, etc.)
            collection_config: Optional dict with base_url, default_headers

        Returns:
            List of result dicts compatible with APIRequestResult schema
        """
        unified = []
        base_url = (collection_config or {}).get("base_url") or ""
        default_headers = (collection_config or {}).get("default_headers") or {}
        requests_list = original_requests or []

        for i, scenario in enumerate(results):
            # Convert steps to assertion-like results
            assertion_results = []
            for step in scenario.steps:
                assertion_results.append({
                    "type": "karate_step",
                    "name": f"{step['keyword']} {step['name']}",
                    "passed": step["status"] == "passed",
                    "message": step.get("error_message") or f"Step {step['status']}",
                })

            # Serialize response body if it's not a string
            response_body = scenario.response_body
            if response_body is not None and not isinstance(response_body, str):
                try:
                    response_body = json.dumps(response_body)
                except (TypeError, ValueError):
                    response_body = str(response_body)

            # Serialize request body if it's not a string
            request_body = scenario.request_body
            if request_body is not None and not isinstance(request_body, str):
                try:
                    request_body = json.dumps(request_body)
                except (TypeError, ValueError):
                    request_body = str(request_body)

            # Request/response from HTTP capture (if any)
            resolved_url = scenario.request_url
            resolved_method = scenario.request_method
            resolved_headers = scenario.request_headers
            resolved_body = request_body

            # Always merge in original_requests when provided so UI always has method/URL/body
            if i < len(requests_list):
                req = requests_list[i]
                path = (req.get("url_path") or "").strip()
                # Always set URL and method from collection so they are never missing
                if path.startswith("http"):
                    resolved_url = path
                else:
                    resolved_url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/")) if base_url else (path or "/")
                resolved_method = req.get("method") or "GET"
                if resolved_headers is None:
                    merged = dict(default_headers)
                    merged.update((req.get("headers") or {}))
                    resolved_headers = merged if merged else {}
                if resolved_body is None and req.get("body"):
                    body_cfg = req["body"]
                    if isinstance(body_cfg, dict) and body_cfg.get("content") is not None:
                        resolved_body = json.dumps(body_cfg["content"]) if body_cfg.get("type") == "json" else str(body_cfg.get("content", ""))
                    elif isinstance(body_cfg, (dict, list)):
                        resolved_body = json.dumps(body_cfg)
                    else:
                        resolved_body = str(body_cfg) if body_cfg is not None else None

            response_status = scenario.response_status
            if response_status is not None and not isinstance(response_status, int):
                try:
                    response_status = int(response_status)
                except (TypeError, ValueError):
                    response_status = None

            unified.append({
                "execution_order": i,
                "status": scenario.status,
                "name": scenario.name,
                "duration_ms": scenario.duration_ms,
                "assertion_results": assertion_results,
                "error_message": scenario.error_message,
                "tags": scenario.tags,
                # HTTP request details
                "resolved_url": resolved_url,
                "resolved_method": resolved_method,
                "resolved_headers": resolved_headers,
                "resolved_body": resolved_body,
                # HTTP response details
                "response_status": response_status,
                "response_headers": scenario.response_headers,
                "response_body": response_body,
                "response_time_ms": scenario.response_time_ms,
            })

        return unified

    async def get_queue_length(self) -> int:
        """Get number of jobs waiting in queue."""
        redis = await self._get_redis()
        return await redis.llen(self.job_queue)

    async def get_worker_stats(self) -> dict:
        """
        Get statistics about worker pool.

        Note: This requires workers to publish heartbeats.
        Basic implementation returns queue stats.
        """
        redis = await self._get_redis()

        queue_length = await redis.llen(self.job_queue)

        # Could extend to track worker heartbeats
        return {
            "queue_length": queue_length,
            "workers_active": 0,  # Would need worker heartbeat tracking
        }
