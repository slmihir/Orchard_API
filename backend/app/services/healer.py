"""Self-healing service for failed test steps using LLM."""

import json
from typing import Optional
from dataclasses import dataclass

from app.services.llm_providers import get_llm_provider, LLMProvider
from app.config import get_settings

settings = get_settings()


HEALING_SYSTEM_PROMPT = """You are a QA automation expert specializing in fixing broken Playwright/Selenium selectors.

Your task: When a test step fails because an element wasn't found, analyze the page and suggest the correct selector.

Rules:
1. Prefer stable selectors in this order: data-testid > id > name > role > class > xpath
2. Consider that the page may have changed since the test was recorded
3. Look for elements with similar purpose/intent, not just similar structure
4. Return ONLY valid JSON, no markdown or explanation outside JSON
5. If you cannot find a suitable element, return confidence: 0"""


HEALING_PROMPT_TEMPLATE = """A test step failed because the selector couldn't find an element.

## Failed Step
- Type: {step_type}
- Original Selector: `{selector}`
- Action Value: {value}
- Error: {error_message}

## Current Page
- URL: {current_url}
- Title: {page_title}

## Available Elements on Page
### Input Fields
```json
{inputs_json}
```

### Buttons
```json
{buttons_json}
```

### Links
```json
{links_json}
```

### Other Clickables
```json
{clickables_json}
```

### Forms
```json
{forms_json}
```

## Your Task
Find the element that matches the original intent of the failed step. The original selector `{selector}` was trying to target an element for a "{step_type}" action.

Respond with ONLY this JSON (no other text):
{{
  "suggested_selector": "the new CSS selector or xpath",
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation of why this matches",
  "selector_type": "css" or "xpath" or "text",
  "alternative_selectors": ["backup1", "backup2"],
  "element_found": true or false
}}"""


@dataclass
class HealingSuggestion:
    """Represents a healing suggestion from the LLM."""
    suggested_selector: str
    confidence: float
    reasoning: str
    selector_type: str
    alternative_selectors: list[str]
    element_found: bool

    @classmethod
    def from_dict(cls, data: dict) -> "HealingSuggestion":
        return cls(
            suggested_selector=data.get("suggested_selector", ""),
            confidence=data.get("confidence", 0.0),
            reasoning=data.get("reasoning", ""),
            selector_type=data.get("selector_type", "css"),
            alternative_selectors=data.get("alternative_selectors", []),
            element_found=data.get("element_found", False),
        )

    def to_dict(self) -> dict:
        return {
            "suggested_selector": self.suggested_selector,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "selector_type": self.selector_type,
            "alternative_selectors": self.alternative_selectors,
            "element_found": self.element_found,
        }


class HealerConfig:
    """Configuration for the healer."""
    def __init__(
        self,
        enabled: bool = True,
        auto_approve: bool = True,
        auto_approve_threshold: float = 0.85,
        mode: str = "inline",
        provider: str = "gemini",
    ):
        self.enabled = enabled
        self.auto_approve = auto_approve
        self.auto_approve_threshold = auto_approve_threshold
        self.mode = mode
        self.provider = provider

    @classmethod
    def from_settings(cls, user_settings) -> "HealerConfig":
        """Create config from UserSettings model."""
        return cls(
            enabled=user_settings.healing_enabled,
            auto_approve=user_settings.healing_auto_approve,
            auto_approve_threshold=user_settings.healing_auto_approve_threshold,
            mode=user_settings.healing_mode,
            provider=user_settings.healing_provider,
        )

    @classmethod
    def from_env(cls) -> "HealerConfig":
        """Create config from environment/default settings."""
        return cls(
            enabled=settings.healing_enabled,
            auto_approve_threshold=settings.healing_auto_approve_threshold,
            mode=settings.healing_mode,
        )


class Healer:
    """Self-healing service for test steps."""

    def __init__(self, config: Optional[HealerConfig] = None, provider: Optional[LLMProvider] = None):
        self.config = config or HealerConfig.from_env()
        self.provider = provider or get_llm_provider(self.config.provider)

    async def suggest_fix(self, context: dict, use_vision: bool = True) -> Optional[HealingSuggestion]:
        """
        Analyze failure context and suggest a fix.

        Args:
            context: Dict from ContextCollector.collect()
            use_vision: Whether to include screenshot in LLM call

        Returns:
            HealingSuggestion or None if healing not possible
        """
        failed_step = context.get("failed_step", {})
        page_info = context.get("page", {})
        elements = context.get("elements", {})

        # Build the prompt
        prompt = HEALING_PROMPT_TEMPLATE.format(
            step_type=failed_step.get("type", "unknown"),
            selector=failed_step.get("selector", ""),
            value=failed_step.get("value", ""),
            error_message=context.get("error_message", "Element not found"),
            current_url=page_info.get("url", ""),
            page_title=page_info.get("title", ""),
            inputs_json=json.dumps(elements.get("inputs", [])[:15], indent=2),
            buttons_json=json.dumps(elements.get("buttons", [])[:10], indent=2),
            links_json=json.dumps(elements.get("links", [])[:10], indent=2),
            clickables_json=json.dumps(elements.get("clickables", [])[:10], indent=2),
            forms_json=json.dumps(elements.get("forms", [])[:5], indent=2),
        )

        try:
            if use_vision and context.get("screenshot_b64"):
                response = await self.provider.complete_with_vision(
                    prompt=prompt,
                    image_b64=context["screenshot_b64"],
                    system_prompt=HEALING_SYSTEM_PROMPT,
                )
            else:
                response = await self.provider.complete(
                    prompt=prompt,
                    system_prompt=HEALING_SYSTEM_PROMPT,
                )

            suggestion = self._parse_response(response)
            if suggestion and suggestion.confidence > 0:
                return suggestion
            return None

        except Exception as e:
            print(f"[Healer] Error getting suggestion: {e}")
            return None

    def _parse_response(self, response: str) -> Optional[HealingSuggestion]:
        """Parse LLM response into HealingSuggestion."""
        try:
            response = response.strip()

            if "```json" in response:
                start = response.index("```json") + 7
                end = response.index("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.index("```") + 3
                end = response.index("```", start)
                response = response[start:end].strip()

            data = json.loads(response)
            return HealingSuggestion.from_dict(data)

        except (json.JSONDecodeError, ValueError) as e:
            print(f"[Healer] Failed to parse response: {e}")
            print(f"[Healer] Raw response: {response[:500]}")
            return None

    def should_auto_approve(self, suggestion: HealingSuggestion) -> bool:
        """Check if suggestion meets auto-approval threshold."""
        if not self.config.auto_approve:
            return False
        return suggestion.confidence >= self.config.auto_approve_threshold


class HealingManager:
    """Manages the healing workflow during and after test runs."""

    def __init__(self):
        self.healer = Healer()
        self.pending_suggestions: list[dict] = []

    async def handle_failure(
        self,
        context: dict,
        run_id: str,
        step_index: int,
        inline_mode: bool = True,
    ) -> Optional[dict]:
        """
        Handle a step failure and potentially heal it.

        Args:
            context: Failure context from ContextCollector
            run_id: The current test run ID
            step_index: Index of the failed step
            inline_mode: If True, return suggestion for immediate retry

        Returns:
            dict with healing result if inline_mode and auto-approved,
            or suggestion details for UI display
        """
        if not settings.healing_enabled:
            return None

        suggestion = await self.healer.suggest_fix(context)
        if not suggestion:
            return None

        result = {
            "run_id": run_id,
            "step_index": step_index,
            "original_selector": context["failed_step"].get("selector"),
            "suggested_selector": suggestion.suggested_selector,
            "confidence": suggestion.confidence,
            "reasoning": suggestion.reasoning,
            "alternative_selectors": suggestion.alternative_selectors,
            "auto_approved": False,
        }

        if inline_mode and self.healer.should_auto_approve(suggestion):
            result["auto_approved"] = True
            return result

        # Store for batch review
        self.pending_suggestions.append(result)
        return result

    def get_pending_suggestions(self) -> list[dict]:
        """Get all pending suggestions for batch review."""
        return self.pending_suggestions

    def clear_pending(self):
        """Clear pending suggestions."""
        self.pending_suggestions = []
