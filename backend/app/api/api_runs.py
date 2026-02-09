"""API Test Runs routes - execution and results."""

import json
import logging
from datetime import datetime
from urllib.parse import urljoin
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.db.postgres import get_db, AsyncSessionLocal
from app.models.api_collection import APICollection
from app.models.api_request import APIRequest
from app.models.api_environment import APIEnvironment
from app.models.api_test_run import APITestRun
from app.models.api_request_result import APIRequestResult
from app.models.user import User
from app.schemas.api_test_run import (
    ExecuteCollectionRequest,
    ExecuteSingleRequestRequest,
    APITestRunResponse,
    APITestRunSummary,
    APITestRunDetailResponse,
    APIRequestResultResponse,
)
from app.security import get_current_user, get_user_from_token
from app.utils.tenant import tenant_filter, set_tenant
from app.services.api_testing import APITestEngine
from app.services.api_testing.karate import KarateOrchestrator, KarateConverter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=list[APITestRunSummary])
async def list_runs(
    collection_id: UUID | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List test runs, optionally filtered by collection."""
    query = (
        select(APITestRun)
        .where(tenant_filter(APITestRun, current_user))
        .order_by(APITestRun.created_at.desc())
        .limit(limit)
    )

    if collection_id:
        query = query.where(APITestRun.collection_id == collection_id)

    result = await db.execute(query)
    runs = result.scalars().all()

    # Get collection names
    summaries = []
    for run in runs:
        collection_name = None
        if run.collection_id:
            coll_result = await db.execute(
                select(APICollection.name)
                .where(APICollection.id == run.collection_id)
            )
            collection_name = coll_result.scalar()

        summaries.append(APITestRunSummary(
            id=run.id,
            collection_id=run.collection_id,
            collection_name=collection_name,
            name=run.name,
            trigger_type=run.trigger_type,
            engine=run.engine,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            total_duration_ms=run.total_duration_ms,
            total_requests=run.total_requests,
            passed_requests=run.passed_requests,
            failed_requests=run.failed_requests,
            created_at=run.created_at,
        ))

    return summaries


@router.get("/{run_id}", response_model=APITestRunDetailResponse)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed test run with results."""
    result = await db.execute(
        select(APITestRun)
        .where(
            APITestRun.id == run_id,
            tenant_filter(APITestRun, current_user),
        )
        .options(selectinload(APITestRun.results))
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    # Sort results by execution order and build response list so all fields (e.g. resolved_url) are serialized
    sorted_results = sorted(run.results, key=lambda r: r.execution_order)
    results_payload = [APIRequestResultResponse.model_validate(r) for r in sorted_results]

    if results_payload and run.engine == "karate":
        first = results_payload[0]
        logger.info(
            "GET run Karate first result: resolved_url=%s resolved_method=%s response_status=%s",
            first.resolved_url,
            first.resolved_method,
            first.response_status,
        )

    return APITestRunDetailResponse(
        id=run.id,
        collection_id=run.collection_id,
        name=run.name,
        trigger_type=run.trigger_type,
        trigger_source=run.trigger_source,
        environment_id=run.environment_id,
        engine=run.engine,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        total_duration_ms=run.total_duration_ms,
        total_requests=run.total_requests,
        passed_requests=run.passed_requests,
        failed_requests=run.failed_requests,
        skipped_requests=run.skipped_requests,
        total_assertions=run.total_assertions,
        passed_assertions=run.passed_assertions,
        failed_assertions=run.failed_assertions,
        error_message=run.error_message,
        error_type=run.error_type,
        karate_job_id=run.karate_job_id,
        created_at=run.created_at,
        results=results_payload,
        run_context=run.run_context,
    )


@router.get("/{run_id}/results", response_model=list[APIRequestResultResponse])
async def get_run_results(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get results for a test run."""
    # Verify run access
    run_result = await db.execute(
        select(APITestRun)
        .where(
            APITestRun.id == run_id,
            tenant_filter(APITestRun, current_user),
        )
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test run not found")

    result = await db.execute(
        select(APIRequestResult)
        .where(APIRequestResult.test_run_id == run_id)
        .order_by(APIRequestResult.execution_order)
    )
    results = result.scalars().all()

    return [APIRequestResultResponse.model_validate(r) for r in results]


@router.delete("/{run_id}")
async def delete_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a test run and its results."""
    result = await db.execute(
        select(APITestRun)
        .where(
            APITestRun.id == run_id,
            tenant_filter(APITestRun, current_user),
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    await db.delete(run)
    await db.commit()

    return {"status": "deleted"}


@router.post("/execute/collection/{collection_id}", response_model=APITestRunResponse)
async def execute_collection(
    collection_id: UUID,
    data: ExecuteCollectionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute an API collection (non-streaming)."""
    data = data or ExecuteCollectionRequest()

    # Load collection with requests
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

    # Load environment if specified
    environment = None
    if data.environment_id:
        env_result = await db.execute(
            select(APIEnvironment)
            .where(APIEnvironment.id == data.environment_id)
        )
        environment = env_result.scalar_one_or_none()

    # Determine engine
    engine = data.engine or collection.default_engine

    # Create test run record
    test_run = APITestRun(
        collection_id=collection.id,
        trigger_type="manual",
        environment_id=data.environment_id,
        engine=engine,
        status="running",
        started_at=datetime.utcnow(),
    )
    set_tenant(test_run, current_user)
    db.add(test_run)
    await db.flush()

    try:
        if engine == "karate":
            # Execute with Karate
            await _execute_with_karate(
                test_run=test_run,
                collection=collection,
                environment=environment,
                data=data,
                db=db,
            )
        else:
            # Execute with Python engine
            await _execute_with_python(
                test_run=test_run,
                collection=collection,
                environment=environment,
                data=data,
                db=db,
            )

        await db.commit()
        await db.refresh(test_run)

    except Exception as e:
        test_run.status = "error"
        test_run.error_message = str(e)
        test_run.error_type = "execution"
        test_run.finished_at = datetime.utcnow()
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    return APITestRunResponse.model_validate(test_run)


async def _execute_with_python(
    test_run: APITestRun,
    collection: APICollection,
    environment: APIEnvironment | None,
    data: ExecuteCollectionRequest,
    db: AsyncSession,
):
    """Execute collection using Python engine."""
    # Build config dicts
    collection_config = {
        "base_url": collection.base_url,
        "auth_config": collection.auth_config,
        "variables": collection.variables,
        "default_headers": collection.default_headers,
    }

    environment_config = None
    if environment:
        environment_config = {
            "base_url": environment.base_url,
            "auth_config": environment.auth_config,
            "variables": environment.variables,
            "default_headers": environment.default_headers,
        }

    # Convert requests to dicts
    requests = [
        {
            "id": r.id,
            "name": r.name,
            "method": r.method,
            "url_path": r.url_path,
            "headers": r.headers,
            "query_params": r.query_params,
            "body": r.body,
            "assertions": r.assertions,
            "variable_extractions": r.variable_extractions,
            "order_index": r.order_index,
            "timeout_ms": r.timeout_ms,
        }
        for r in collection.requests
    ]

    # Execute
    engine = APITestEngine()
    try:
        result = await engine.execute_collection(
            requests=requests,
            collection_config=collection_config,
            environment_config=environment_config,
            runtime_variables=data.variables,
            request_ids=data.request_ids,
            stop_on_failure=data.stop_on_failure,
        )

        # Save results
        for exec_result in result.results:
            request_result = APIRequestResult(
                test_run_id=test_run.id,
                request_id=exec_result.request_id,
                execution_order=result.results.index(exec_result),
                status=exec_result.status,
                resolved_url=exec_result.resolved_url,
                resolved_headers=exec_result.resolved_headers,
                resolved_body=exec_result.resolved_body,
                response_status=exec_result.response.status_code if exec_result.response else None,
                response_headers=exec_result.response.headers if exec_result.response else None,
                response_body=exec_result.response.body[:10000] if exec_result.response else None,
                response_size_bytes=exec_result.response.size_bytes if exec_result.response else None,
                started_at=exec_result.started_at,
                finished_at=exec_result.finished_at,
                duration_ms=exec_result.duration_ms,
                assertion_results=exec_result.assertion_results,
                extracted_variables=exec_result.extracted_variables,
                error_message=exec_result.error_message,
                error_type=exec_result.error_type,
            )
            db.add(request_result)

        # Update test run
        test_run.status = "passed" if result.all_passed else "failed"
        test_run.finished_at = datetime.utcnow()
        test_run.total_duration_ms = result.duration_ms
        test_run.total_requests = result.total
        test_run.passed_requests = result.passed
        test_run.failed_requests = result.failed
        test_run.skipped_requests = result.skipped
        test_run.total_assertions = result.total_assertions
        test_run.passed_assertions = result.passed_assertions
        test_run.failed_assertions = result.failed_assertions

    finally:
        await engine.close()


async def _execute_with_karate(
    test_run: APITestRun,
    collection: APICollection,
    environment: APIEnvironment | None,
    data: ExecuteCollectionRequest,
    db: AsyncSession,
):
    """Execute collection using Karate engine."""
    # Convert collection to Karate feature
    converter = KarateConverter()

    collection_dict = {
        "name": collection.name,
        "description": collection.description,
        "base_url": environment.base_url if environment and environment.base_url else collection.base_url,
        "auth_config": environment.auth_config if environment and environment.auth_config else collection.auth_config,
        "default_headers": environment.default_headers if environment and environment.default_headers else collection.default_headers,
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

    feature_content = converter.requests_to_feature(requests_list, collection_dict)

    # #region agent log
    try:
        import urllib.request

        log_data = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A",
            "location": "api_runs.py:403",
            "message": "Generated Karate feature file",
            "data": {
                "collection_id": str(collection.id),
                "collection_name": collection.name,
                "feature_length": len(feature_content),
                "feature_preview": feature_content[:500],
                "requests_count": len(requests_list),
            },
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
        }
        req = urllib.request.Request(
            "http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80",
            data=json.dumps(log_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=0.5)
    except Exception:
        pass
    # #endregion

    # Build environment variables
    env_vars = {}
    if environment and environment.variables:
        for key, val in environment.variables.items():
            if isinstance(val, dict) and "value" in val:
                env_vars[key] = val["value"]
            else:
                env_vars[key] = val

    if data.variables:
        env_vars.update(data.variables)

    # Submit to Karate queue
    orchestrator = KarateOrchestrator()
    try:
        job_id = await orchestrator.submit_feature(
            feature_content=feature_content,
            env_vars=env_vars,
        )

        test_run.karate_job_id = job_id

        # Wait for result
        job_result = await orchestrator.get_result(job_id, timeout_seconds=300)

        # #region agent log
        try:
            import urllib.request

            log_data = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "C,E",
                "location": "api_runs.py:428",
                "message": "Karate job result received",
                "data": {
                    "job_id": job_id,
                    "status": job_result.status,
                    "has_parsed_results": job_result.parsed_results is not None,
                    "parsed_results_count": len(job_result.parsed_results) if job_result.parsed_results else 0,
                    "has_cucumber_report": job_result.cucumber_report is not None,
                    "error": job_result.error,
                    "duration_ms": job_result.duration_ms,
                },
                "timestamp": int(datetime.utcnow().timestamp() * 1000),
            }
            req = urllib.request.Request(
                "http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80",
                data=json.dumps(log_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.5)
        except Exception:
            pass
        # #endregion

        if job_result.status == "error":
            test_run.status = "error"
            test_run.error_message = job_result.error
            test_run.error_type = "karate"
        elif job_result.status == "timeout":
            test_run.status = "error"
            test_run.error_message = "Karate job timed out"
            test_run.error_type = "timeout"
        else:
            # Parse results
            if job_result.parsed_results:
                # #region agent log
                try:
                    import urllib.request

                    log_data = {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "E",
                        "location": "api_runs.py:440",
                        "message": "Before parsing Karate results",
                        "data": {
                            "parsed_results_count": len(job_result.parsed_results),
                            "first_result": str(job_result.parsed_results[0]) if job_result.parsed_results else None,
                        },
                        "timestamp": int(datetime.utcnow().timestamp() * 1000),
                    }
                    req = urllib.request.Request(
                        "http://127.0.0.1:7242/ingest/ffd5fa03-dbab-4fa7-aaaf-9a9dfba56c80",
                        data=json.dumps(log_data).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    urllib.request.urlopen(req, timeout=0.5)
                except Exception:
                    pass
                # #endregion
                unified_results = orchestrator.results_to_unified_format(
                    job_result.parsed_results,
                    original_requests=requests_list,
                    collection_config=collection_dict,
                )
                # #endregion

                logger.info(
                    "Karate unified_results: requests_list_len=%s parsed_len=%s unified_len=%s first_resolved_url=%s first_resolved_method=%s",
                    len(requests_list),
                    len(job_result.parsed_results or []),
                    len(unified_results),
                    unified_results[0].get("resolved_url") if unified_results else None,
                    unified_results[0].get("resolved_method") if unified_results else None,
                )

                passed = sum(1 for r in unified_results if r["status"] == "passed")
                failed = sum(1 for r in unified_results if r["status"] == "failed")

                # Aggregate assertion counts from each result so run summary shows correct totals
                total_assertions = 0
                passed_assertions = 0
                for r in unified_results:
                    assertion_list = r.get("assertion_results") or []
                    total_assertions += len(assertion_list)
                    passed_assertions += sum(1 for a in assertion_list if a.get("passed") is True)

                test_run.status = "passed" if failed == 0 else "failed"
                test_run.total_requests = len(unified_results)
                test_run.passed_requests = passed
                test_run.failed_requests = failed
                test_run.total_assertions = total_assertions
                test_run.passed_assertions = passed_assertions
                test_run.failed_assertions = total_assertions - passed_assertions

                # Save results; map each scenario to the corresponding request by index
                sorted_requests = sorted(collection.requests, key=lambda x: x.order_index) if collection.requests else []
                base_url = collection_dict.get("base_url") or ""
                default_headers = collection_dict.get("default_headers") or {}

                for idx, res in enumerate(unified_results):
                    # Truncate response body if too large
                    response_body = res.get("response_body")
                    if response_body and len(response_body) > 10000:
                        response_body = response_body[:10000]

                    # Start from unified result; then always fill from collection when we have the request
                    # so Karate runs never have missing request details in the UI
                    resolved_url = res.get("resolved_url")
                    resolved_method = res.get("resolved_method")
                    resolved_headers = res.get("resolved_headers")
                    resolved_body = res.get("resolved_body")

                    if idx < len(requests_list):
                        req = requests_list[idx]
                        path = (req.get("url_path") or "").strip()
                        if not resolved_url:
                            resolved_url = path if path.startswith("http") else (urljoin(base_url.rstrip("/") + "/", path.lstrip("/")) if base_url else (path or "/"))
                        if not resolved_method:
                            resolved_method = req.get("method") or "GET"
                        if resolved_headers is None:
                            merged = dict(default_headers)
                            merged.update((req.get("headers") or {}))
                            resolved_headers = merged
                        if resolved_body is None and req.get("body"):
                            body_cfg = req["body"]
                            if isinstance(body_cfg, dict) and body_cfg.get("content") is not None:
                                resolved_body = json.dumps(body_cfg["content"]) if body_cfg.get("type") == "json" else str(body_cfg.get("content", ""))
                            elif isinstance(body_cfg, (dict, list)):
                                resolved_body = json.dumps(body_cfg)
                            else:
                                resolved_body = str(body_cfg) if body_cfg is not None else None

                    req_at_idx = sorted_requests[idx] if idx < len(sorted_requests) else (sorted_requests[0] if sorted_requests else None)
                    request_id = req_at_idx.id if req_at_idx else None
                    if not request_id and sorted_requests:
                        request_id = sorted_requests[0].id

                    if idx == 0:
                        logger.info(
                            "Karate saving first result: resolved_url=%s resolved_method=%s response_status=%s",
                            resolved_url,
                            resolved_method,
                            res.get("response_status"),
                        )

                    request_result = APIRequestResult(
                        test_run_id=test_run.id,
                        request_id=request_id,
                        execution_order=idx,
                        status=res["status"],
                        duration_ms=res.get("duration_ms"),
                        assertion_results=res.get("assertion_results"),
                        error_message=res.get("error_message"),
                        # HTTP request details
                        resolved_url=resolved_url,
                        resolved_method=resolved_method,
                        resolved_headers=resolved_headers,
                        resolved_body=resolved_body,
                        # HTTP response details
                        response_status=res.get("response_status"),
                        response_headers=res.get("response_headers"),
                        response_body=response_body,
                    )
                    db.add(request_result)

        test_run.finished_at = datetime.utcnow()
        test_run.total_duration_ms = job_result.duration_ms

    finally:
        await orchestrator.close()


@router.post("/execute/request/{request_id}", response_model=APIRequestResultResponse)
async def execute_single_request(
    request_id: UUID,
    data: ExecuteSingleRequestRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute a single API request."""
    data = data or ExecuteSingleRequestRequest()

    # Load request with collection
    result = await db.execute(
        select(APIRequest)
        .join(APICollection)
        .where(
            APIRequest.id == request_id,
            tenant_filter(APICollection, current_user),
        )
        .options(selectinload(APIRequest.collection))
    )
    request = result.scalar_one_or_none()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    collection = request.collection

    # Load environment if specified
    environment = None
    if data.environment_id:
        env_result = await db.execute(
            select(APIEnvironment)
            .where(APIEnvironment.id == data.environment_id)
        )
        environment = env_result.scalar_one_or_none()

    # Build configs
    collection_config = {
        "base_url": collection.base_url,
        "auth_config": collection.auth_config,
        "variables": collection.variables,
        "default_headers": collection.default_headers,
    }

    environment_config = None
    if environment:
        environment_config = {
            "base_url": environment.base_url,
            "auth_config": environment.auth_config,
            "variables": environment.variables,
            "default_headers": environment.default_headers,
        }

    request_dict = {
        "id": request.id,
        "name": request.name,
        "method": request.method,
        "url_path": request.url_path,
        "headers": request.headers,
        "query_params": request.query_params,
        "body": request.body,
        "assertions": request.assertions,
        "variable_extractions": request.variable_extractions,
        "timeout_ms": request.timeout_ms,
    }

    # Execute
    engine = APITestEngine()
    try:
        exec_result = await engine.execute_single_request(
            request=request_dict,
            collection_config=collection_config,
            environment_config=environment_config,
        )

        return APIRequestResultResponse(
            id=request.id,
            test_run_id=request.id,  # No test run for single execution
            request_id=request.id,
            execution_order=0,
            status=exec_result.status,
            resolved_url=exec_result.resolved_url,
            resolved_method=request.method,
            resolved_headers=exec_result.resolved_headers,
            resolved_body=exec_result.resolved_body,
            response_status=exec_result.response.status_code if exec_result.response else None,
            response_headers=exec_result.response.headers if exec_result.response else None,
            response_body=exec_result.response.body[:10000] if exec_result.response else None,
            response_size_bytes=exec_result.response.size_bytes if exec_result.response else None,
            started_at=exec_result.started_at,
            finished_at=exec_result.finished_at,
            duration_ms=exec_result.duration_ms,
            assertion_results=exec_result.assertion_results,
            extracted_variables=exec_result.extracted_variables,
            error_message=exec_result.error_message,
            error_type=exec_result.error_type,
            created_at=datetime.utcnow(),
        )

    finally:
        await engine.close()


@router.websocket("/ws/execute/{collection_id}")
async def execute_websocket(
    websocket: WebSocket,
    collection_id: str,
    token: str | None = None,
):
    """Execute collection with WebSocket streaming."""
    await websocket.accept()

    try:
        # Authenticate
        async with AsyncSessionLocal() as db:
            current_user = await get_user_from_token(token, db) if token else None
            if not current_user:
                await websocket.send_json({"type": "error", "data": {"message": "Unauthorized"}})
                await websocket.close()
                return

            # Load collection
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
                await websocket.send_json({"type": "error", "data": {"message": "Collection not found"}})
                await websocket.close()
                return

        # Wait for start command
        start_data = await websocket.receive_json()
        if start_data.get("type") != "start":
            await websocket.send_json({"type": "error", "data": {"message": "Expected start command"}})
            return

        environment_id = start_data.get("environment_id")
        request_ids = start_data.get("request_ids")
        engine_type = start_data.get("engine") or collection.default_engine
        variables = start_data.get("variables")

        # Load environment
        environment = None
        async with AsyncSessionLocal() as db:
            if environment_id:
                env_result = await db.execute(
                    select(APIEnvironment)
                    .where(APIEnvironment.id == environment_id)
                )
                environment = env_result.scalar_one_or_none()

            # Create test run
            test_run = APITestRun(
                collection_id=collection.id,
                trigger_type="manual",
                environment_id=environment_id,
                engine=engine_type,
                status="running",
                started_at=datetime.utcnow(),
            )
            set_tenant(test_run, current_user)
            db.add(test_run)
            await db.commit()
            run_id = test_run.id

        await websocket.send_json({
            "type": "status",
            "data": {"status": "running", "run_id": str(run_id)},
        })

        # Build configs
        collection_config = {
            "base_url": collection.base_url,
            "auth_config": collection.auth_config,
            "variables": collection.variables,
            "default_headers": collection.default_headers,
        }

        environment_config = None
        if environment:
            environment_config = {
                "base_url": environment.base_url,
                "auth_config": environment.auth_config,
                "variables": environment.variables,
                "default_headers": environment.default_headers,
            }

        requests = [
            {
                "id": r.id,
                "name": r.name,
                "method": r.method,
                "url_path": r.url_path,
                "headers": r.headers,
                "query_params": r.query_params,
                "body": r.body,
                "assertions": r.assertions,
                "variable_extractions": r.variable_extractions,
                "order_index": r.order_index,
                "timeout_ms": r.timeout_ms,
            }
            for r in collection.requests
        ]

        # Streaming callbacks
        async def on_request_start(data):
            await websocket.send_json({"type": "request_start", "data": data})

        async def on_request_complete(data):
            await websocket.send_json({"type": "request_complete", "data": data})

        async def on_assertion_result(data):
            await websocket.send_json({"type": "assertion", "data": data})

        async def on_variable_extracted(data):
            await websocket.send_json({"type": "variable", "data": data})

        # Execute
        engine = APITestEngine(
            on_request_start=on_request_start,
            on_request_complete=on_request_complete,
            on_assertion_result=on_assertion_result,
            on_variable_extracted=on_variable_extracted,
        )

        try:
            result = await engine.execute_collection(
                requests=requests,
                collection_config=collection_config,
                environment_config=environment_config,
                runtime_variables=variables,
                request_ids=[UUID(rid) for rid in request_ids] if request_ids else None,
            )

            # Save results to database
            async with AsyncSessionLocal() as db:
                run_result = await db.execute(
                    select(APITestRun).where(APITestRun.id == run_id)
                )
                test_run = run_result.scalar_one()

                for exec_result in result.results:
                    request_result = APIRequestResult(
                        test_run_id=test_run.id,
                        request_id=exec_result.request_id,
                        execution_order=result.results.index(exec_result),
                        status=exec_result.status,
                        resolved_url=exec_result.resolved_url,
                        resolved_headers=exec_result.resolved_headers,
                        resolved_body=exec_result.resolved_body,
                        response_status=exec_result.response.status_code if exec_result.response else None,
                        response_headers=exec_result.response.headers if exec_result.response else None,
                        response_body=exec_result.response.body[:10000] if exec_result.response else None,
                        duration_ms=exec_result.duration_ms,
                        assertion_results=exec_result.assertion_results,
                        extracted_variables=exec_result.extracted_variables,
                        error_message=exec_result.error_message,
                    )
                    db.add(request_result)

                test_run.status = "passed" if result.all_passed else "failed"
                test_run.finished_at = datetime.utcnow()
                test_run.total_duration_ms = result.duration_ms
                test_run.total_requests = result.total
                test_run.passed_requests = result.passed
                test_run.failed_requests = result.failed
                test_run.skipped_requests = result.skipped
                test_run.total_assertions = result.total_assertions
                test_run.passed_assertions = result.passed_assertions
                test_run.failed_assertions = result.failed_assertions

                await db.commit()

            await websocket.send_json({
                "type": "complete",
                "data": {
                    "run_id": str(run_id),
                    "status": "passed" if result.all_passed else "failed",
                    "summary": result.summary,
                },
            })

        finally:
            await engine.close()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "data": {"message": str(e)}})
