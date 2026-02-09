from pydantic import BaseModel
from typing import Literal
from uuid import UUID


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: UUID | None = None


class ChatResponse(BaseModel):
    message: str
    session_id: UUID


class AgentAction(BaseModel):
    type: Literal["navigate", "click", "fill", "wait", "scroll", "hover", "assert"]
    selector: str | None = None
    value: str | None = None
    screenshot: str | None = None  # base64 encoded
    timestamp: str


class BrowserUpdate(BaseModel):
    type: Literal["screenshot", "action", "status", "error", "complete"]
    data: dict
