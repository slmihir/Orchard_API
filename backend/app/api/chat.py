from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import json
import uuid
import asyncio

from app.db.postgres import get_db
from app.services.agent import BrowserAgent
from app.services.llm import get_llm_client
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()

# Store active sessions
active_sessions: dict[str, dict] = {}


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    if session_id not in active_sessions:
        active_sessions[session_id] = {
            "messages": [],
            "agent": None,
            "steps": []
        }

    session = active_sessions[session_id]

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "chat":
                # User sent a chat message
                user_message = message["content"]
                session["messages"].append({"role": "user", "content": user_message})

                await websocket.send_json({"type": "status", "data": {"status": "thinking"}})

                llm = get_llm_client()
                response = await llm.process_message(
                    messages=session["messages"],
                    context={
                        "steps": session["steps"],
                        "has_browser": session["agent"] is not None
                    }
                )

                # If LLM decided to start browser automation
                if response.get("start_automation"):
                    # Simple acknowledgment, skip verbose LLM response
                    session["messages"].append({"role": "assistant", "content": "On it..."})
                    await websocket.send_json({
                        "type": "chat",
                        "data": {"role": "assistant", "content": "On it..."}
                    })
                    await start_browser_automation(
                        websocket,
                        session,
                        response["task"],
                        response.get("url")
                    )
                else:
                    # No automation - send the LLM response
                    session["messages"].append({"role": "assistant", "content": response["message"]})
                    await websocket.send_json({
                        "type": "chat",
                        "data": {"role": "assistant", "content": response["message"]}
                    })

            elif message["type"] == "start_automation":
                # Explicit request to start automation
                await start_browser_automation(
                    websocket,
                    session,
                    message["task"],
                    message.get("url")
                )

            elif message["type"] == "stop_automation":
                # Stop current automation
                if session["agent"]:
                    await session["agent"].stop()
                    session["agent"] = None
                    await websocket.send_json({
                        "type": "status",
                        "data": {"status": "stopped"}
                    })

    except WebSocketDisconnect:
        # Cleanup
        if session_id in active_sessions:
            if active_sessions[session_id]["agent"]:
                await active_sessions[session_id]["agent"].stop()
            del active_sessions[session_id]


async def start_browser_automation(websocket: WebSocket, session: dict, task: str, url: str | None):
    """Start browser automation and stream updates."""

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

    # Reuse existing agent or create new one
    if session["agent"] is None:
        await websocket.send_json({
            "type": "status",
            "data": {"status": "starting_browser"}
        })
        agent = BrowserAgent(
            on_action=on_action,
            on_screenshot=on_screenshot
        )
        session["agent"] = agent
        is_new_browser = True
    else:
        agent = session["agent"]
        agent.on_action = on_action
        agent.on_screenshot = on_screenshot
        is_new_browser = False

    try:
        await websocket.send_json({
            "type": "status",
            "data": {"status": "running"}
        })

        # Run the agent - only pass URL if it's a new browser
        result = await agent.run(task, start_url=url if is_new_browser else None)

        # Use agent's message if it's descriptive (e.g., for assertions)
        completion_message = result.get("message", "Done" if result["success"] else "Failed")
        # Simplify generic success messages
        if completion_message == "Automation completed successfully":
            completion_message = "Done"

        await websocket.send_json({
            "type": "complete",
            "data": {
                "success": result["success"],
                "steps": session["steps"],
                "message": completion_message
            }
        })

        # Keep browser alive - don't stop it!

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "data": {"message": str(e)}
        })
        # Only stop on error
        await agent.stop()
        session["agent"] = None


@router.post("/session")
async def create_session():
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "messages": [],
        "agent": None,
        "steps": []
    }
    return {"session_id": session_id}
