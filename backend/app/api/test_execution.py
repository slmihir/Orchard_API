"""WebSocket endpoint for test case execution via browser-use."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import json
import uuid
import asyncio
from datetime import datetime
from typing import Optional

from app.db.postgres import AsyncSessionLocal
from app.services.agent import BrowserAgent
from app.services.test_case_service import TestCaseService
from app.models.test_case import TestCase
from app.models.project import Project, DiscoveredPage

router = APIRouter()

# Store active test execution sessions
active_test_sessions: dict[str, dict] = {}


@router.websocket("/ws/test/{test_id}")
async def test_execution_websocket(websocket: WebSocket, test_id: str):
    """WebSocket endpoint for executing a single test case."""
    await websocket.accept()

    session_id = str(uuid.uuid4())
    active_test_sessions[session_id] = {
        "test_id": test_id,
        "agent": None,
        "steps": [],
        "status": "pending",
        "start_time": None,
    }
    session = active_test_sessions[session_id]

    db = AsyncSessionLocal()
    try:
        test_case = await db.get(TestCase, uuid.UUID(test_id))
        if not test_case:
            await websocket.send_json({
                "type": "error",
                "data": {"message": f"Test case {test_id} not found"}
            })
            await db.close()
            return

        project = await db.get(Project, test_case.project_id)
        if not project:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Project not found"}
            })
            await db.close()
            return

        page = None
        if test_case.page_id:
            page = await db.get(DiscoveredPage, test_case.page_id)

        # Determine start URL - use page URL if available, otherwise base URL
        start_url = page.url if page else project.base_url

        # Wait for start command
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "start":
                await run_test_execution(
                    websocket=websocket,
                    session=session,
                    db=db,
                    test_case=test_case,
                    start_url=start_url,
                )
                break

            elif message["type"] == "stop":
                if session["agent"]:
                    await session["agent"].stop()
                    session["agent"] = None
                await websocket.send_json({
                    "type": "status",
                    "data": {"status": "stopped"}
                })
                break

    except WebSocketDisconnect:
        pass
    finally:
        await db.close()
        # Cleanup
        if session_id in active_test_sessions:
            if active_test_sessions[session_id]["agent"]:
                try:
                    await active_test_sessions[session_id]["agent"].stop()
                except Exception:
                    pass
            del active_test_sessions[session_id]


async def run_test_execution(
    websocket: WebSocket,
    session: dict,
    db: AsyncSession,
    test_case: TestCase,
    start_url: str,
):
    """Execute a test case using browser-use."""

    session["status"] = "running"
    session["start_time"] = datetime.utcnow()
    session["steps"] = []

    # Callbacks for streaming actions and screenshots
    async def on_action(action: dict):
        session["steps"].append(action)
        await websocket.send_json({
            "type": "action",
            "data": action
        })

    async def on_screenshot(screenshot: str):
        await websocket.send_json({
            "type": "screenshot",
            "data": {"image": screenshot}
        })

    try:
        await websocket.send_json({
            "type": "status",
            "data": {"status": "starting_browser"}
        })

        agent = BrowserAgent(
            on_action=on_action,
            on_screenshot=on_screenshot,
        )
        session["agent"] = agent

        await websocket.send_json({
            "type": "status",
            "data": {"status": "running"}
        })

        # Run the test instruction - start directly at the page URL
        result = await agent.run(
            task=test_case.instruction,
            start_url=start_url,
        )

        # Calculate duration
        end_time = datetime.utcnow()
        duration_ms = int((end_time - session["start_time"]).total_seconds() * 1000)

        # Determine test status
        test_status = "passed" if result.get("success") else "failed"
        error_msg = None if result.get("success") else result.get("message", "Test failed")

        service = TestCaseService(db)
        await service.update_test_steps(test_case.id, session["steps"])
        await service.update_test_result(
            test_case_id=test_case.id,
            status=test_status,
            duration=duration_ms,
            error=error_msg,
        )

        await websocket.send_json({
            "type": "complete",
            "data": {
                "success": result.get("success", False),
                "status": test_status,
                "steps": session["steps"],
                "duration": duration_ms,
                "message": result.get("message", "Test completed"),
            }
        })

    except Exception as e:
        try:
            end_time = datetime.utcnow()
            duration_ms = int((end_time - session["start_time"]).total_seconds() * 1000) if session["start_time"] else 0

            service = TestCaseService(db)
            await service.update_test_result(
                test_case_id=test_case.id,
                status="failed",
                duration=duration_ms,
                error=str(e),
            )
        except Exception:
            pass

        await websocket.send_json({
            "type": "error",
            "data": {"message": str(e)}
        })

    finally:
        # Stop browser
        if session["agent"]:
            try:
                await session["agent"].stop()
            except Exception:
                pass
            session["agent"] = None
