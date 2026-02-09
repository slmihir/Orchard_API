"""Configurable LLM provider abstraction for healing and other AI features."""

import json
import base64
from abc import ABC, abstractmethod
from typing import Optional
from app.config import get_settings

settings = get_settings()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete_with_vision(
        self,
        prompt: str,
        image_b64: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Send a prompt with optional image and get a response."""
        pass

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Send a text-only prompt and get a response."""
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini provider using langchain."""

    def __init__(self):
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage

        self.model = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key,
            temperature=0.3,  # Lower temp for more deterministic healing
        )
        self.HumanMessage = HumanMessage
        self.SystemMessage = SystemMessage

    async def complete_with_vision(
        self,
        prompt: str,
        image_b64: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append(self.SystemMessage(content=system_prompt))

        if image_b64:
            # Gemini vision with image
            messages.append(self.HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]))
        else:
            messages.append(self.HumanMessage(content=prompt))

        response = await self.model.ainvoke(messages)
        return self._extract_content(response.content)

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        return await self.complete_with_vision(prompt, None, system_prompt)

    def _extract_content(self, content) -> str:
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        elif isinstance(content, dict):
            return content.get("text", str(content))
        return str(content)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    def __init__(self):
        import openai
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model or "gpt-4o"

    async def complete_with_vision(
        self,
        prompt: str,
        image_b64: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if image_b64:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                ],
            })
        else:
            messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
        )
        return response.choices[0].message.content

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        return await self.complete_with_vision(prompt, None, system_prompt)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self):
        import anthropic
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model or "claude-sonnet-4-20250514"

    async def complete_with_vision(
        self,
        prompt: str,
        image_b64: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        content = []

        if image_b64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_b64,
                },
            })

        content.append({"type": "text", "text": prompt})

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=system_prompt or "",
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        return await self.complete_with_vision(prompt, None, system_prompt)


def get_llm_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """
    Get an LLM provider by name.

    Args:
        provider_name: One of "gemini", "openai", "anthropic".
                      Defaults to settings.default_llm_provider.

    Returns:
        An LLMProvider instance.
    """
    provider = provider_name or settings.default_llm_provider

    if provider == "gemini":
        return GeminiProvider()
    elif provider == "openai":
        return OpenAIProvider()
    elif provider == "anthropic":
        return AnthropicProvider()
    else:
        # Default to Gemini
        return GeminiProvider()
