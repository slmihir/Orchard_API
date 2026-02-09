from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import os
from app.config import get_settings

settings = get_settings()

# Set the env var for langchain
os.environ["GOOGLE_API_KEY"] = settings.google_api_key

SYSTEM_PROMPT = """You are an AI assistant helping users automate browser actions.

IMPORTANT: When generating automation tasks:
- Browser active: {has_browser}
- If browser is ALREADY ACTIVE (True), the user is continuing from the current page.
  Generate a task for ONLY the current request. Do NOT repeat previous actions like login.
  Do NOT include a URL - omit the "url" field entirely.
- If browser is NOT active (False), this is a fresh start. Include the full task and URL.

When ready to automate, respond with ONLY a JSON block (no other text):
```json
{{
  "start_automation": true,
  "task": "only the current action to perform",
  "url": "starting URL (omit if browser already active)"
}}
```

Examples:
- First request "login to example.com": include url and full login task
- Follow-up "click settings": task is just "click on settings", no url needed
"""


class LLMClient:
    def __init__(self):
        # Validate API key
        api_key = settings.google_api_key
        if not api_key:
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY must be set in .env file")
        if len(api_key) < 35:
            raise ValueError(f"API key appears to be invalid (too short: {len(api_key)} chars). Please check your .env file.")
        if api_key.endswith('-') and len(api_key) < 39:
            raise ValueError("API key appears to be truncated. Please ensure the complete key is in your .env file (no trailing dashes or spaces).")
        
        self.model = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=api_key,
            temperature=0.7
        )

    async def process_message(self, messages: list[dict], context: dict) -> dict:
        """Process a conversation and return response with potential automation trigger."""
        langchain_messages = [
            SystemMessage(content=SYSTEM_PROMPT.format(
                steps_count=len(context.get("steps", [])),
                has_browser=context.get("has_browser", False)
            ))
        ]

        for msg in messages:
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))

        response = await self.model.ainvoke(langchain_messages)

        raw_content = response.content
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            # List of content blocks - extract text from each
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in raw_content
            )
        elif isinstance(raw_content, dict):
            # Single content block with text key
            content = raw_content.get("text", str(raw_content))
        else:
            content = str(raw_content)

        result = {"message": content}

        if "```json" in content:
            try:
                json_start = content.index("```json") + 7
                json_end = content.index("```", json_start)
                json_str = content[json_start:json_end].strip()
                data = json.loads(json_str)

                if data.get("start_automation"):
                    result["start_automation"] = True
                    result["task"] = data["task"]
                    result["url"] = data.get("url")
                    # Clean the message
                    result["message"] = content[:content.index("```json")].strip()
                    if not result["message"]:
                        result["message"] = "Starting browser automation..."
            except (ValueError, json.JSONDecodeError):
                pass

        return result


def get_llm_client() -> LLMClient:
    return LLMClient()
