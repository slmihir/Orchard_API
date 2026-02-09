import asyncio
import base64
import os
import re
from datetime import datetime
from typing import Callable, Awaitable, Optional, Tuple

from app.config import get_settings

settings = get_settings()

# Patterns to detect assertion requests in natural language
ASSERTION_PATTERNS = [
    # Text assertions
    (r'(?:verify|check|assert|ensure|confirm|make sure|validate)\s+(?:that\s+)?(?:the\s+)?(?:page\s+)?(?:shows?|displays?|contains?|has)\s+["\'](.+?)["\']', 'assert_text'),
    (r'(?:verify|check|assert|ensure|confirm|make sure|validate)\s+(?:that\s+)?(?:the\s+)?(?:text|message)\s+["\'](.+?)["\']', 'assert_text'),
    (r'(?:verify|check|assert|ensure|confirm|make sure|validate)\s+["\'](.+?)["\'](?:\s+is\s+(?:shown|displayed|visible))?', 'assert_text'),
    (r'(?:i\s+)?(?:should\s+)?see\s+["\'](.+?)["\']', 'assert_text'),
    # URL assertions
    (r'(?:verify|check|assert|ensure|confirm|make sure|validate)\s+(?:that\s+)?(?:the\s+)?url\s+(?:is|contains?|matches?)\s+["\']?(.+?)["\']?\s*$', 'assert_url'),
    (r'(?:verify|check|assert|ensure|confirm|make sure|validate)\s+(?:that\s+)?(?:i\'?m?\s+)?(?:on|at)\s+(?:the\s+)?["\']?(.+?)["\']?\s*(?:page)?\s*$', 'assert_url'),
    (r'url\s+(?:should\s+)?(?:contain|include|be)\s+["\']?(.+?)["\']?\s*$', 'assert_url'),
    # Visibility assertions
    (r'(?:verify|check|assert|ensure|confirm|make sure|validate)\s+(?:that\s+)?(?:the\s+)?(.+?)\s+(?:is\s+)?visible', 'assert_visible'),
    (r'(?:verify|check|assert|ensure|confirm|make sure|validate)\s+(?:that\s+)?(?:the\s+)?(.+?)\s+(?:is\s+)?(?:hidden|not visible|invisible|gone)', 'assert_hidden'),
    (r'(?:the\s+)?(.+?)\s+(?:should\s+)?(?:be\s+)?(?:visible|shown|displayed)', 'assert_visible'),
    (r'(?:the\s+)?(.+?)\s+(?:should\s+)?(?:not\s+)?(?:be\s+)?(?:hidden|invisible|gone)', 'assert_hidden'),
    # Value assertions
    (r'(?:verify|check|assert|ensure|confirm|make sure|validate)\s+(?:that\s+)?(?:the\s+)?(.+?)\s+(?:has\s+)?value\s+["\'](.+?)["\']', 'assert_value'),
    (r'(?:verify|check|assert|ensure|confirm|make sure|validate)\s+(?:that\s+)?(?:the\s+)?(.+?)\s+(?:equals?|is|contains?)\s+["\'](.+?)["\']', 'assert_value'),
]

# Set env var for browser-use
os.environ["GOOGLE_API_KEY"] = settings.google_api_key


class BrowserAgent:
    """Wrapper around browser-use that captures actions and screenshots."""

    def __init__(
        self,
        on_action: Callable[[dict], Awaitable[None]] = None,
        on_screenshot: Callable[[str], Awaitable[None]] = None
    ):
        self.on_action = on_action
        self.on_screenshot = on_screenshot
        self.agent = None
        self.browser_session = None  # Persistent browser session
        self.running = False
        self.screenshot_task = None
        # Auto-assertion tracking
        self.last_url = None
        self.initial_url = None

    async def _stream_screenshots(self):
        """Stream screenshots from browser-use's browser at regular intervals."""
        print("[Screenshot] Starting screenshot stream, waiting for browser...")
        await asyncio.sleep(3)  # Wait for browser to initialize

        while self.running:
            try:
                if self.browser_session:
                    screenshot_data = await self.browser_session.take_screenshot()
                    if screenshot_data:
                        if isinstance(screenshot_data, bytes):
                            screenshot_b64 = base64.b64encode(screenshot_data).decode('utf-8')
                        else:
                            screenshot_b64 = screenshot_data

                        if self.on_screenshot:
                            await self.on_screenshot(screenshot_b64)
                await asyncio.sleep(0.5)  # ~2 fps
            except Exception as e:
                print(f"[Screenshot] Error: {e}")
                await asyncio.sleep(1)

    def _build_selector(self, selector_info: dict, fallback_index: int = None) -> str:
        """Build a Playwright-compatible selector from element info.

        Creates compound selectors when single attributes might match multiple elements.
        """
        if not selector_info:
            return f"[data-index='{fallback_index}']" if fallback_index else None

        attrs = selector_info.get('attributes', {})
        tag = selector_info.get('tag', '').lower()

        # Helper to escape selector values
        def escape_attr(val: str) -> str:
            if not val:
                return val
            return val.replace("'", "\\'").replace('"', '\\"')

        # Strategy: Build compound selectors for uniqueness
        # Combine multiple attributes when available

        # 1. Unique id is always best (if it doesn't look auto-generated)
        elem_id = attrs.get('id', '')
        if elem_id and not any(x in elem_id.lower() for x in ['react-', 'ember-', ':r', 'radix-']):
            return f"#{escape_attr(elem_id)}"

        # 2. name attribute - usually unique for form fields
        name = attrs.get('name', '')
        if name:
            # Combine with tag for specificity
            if tag:
                return f"{tag}[name='{escape_attr(name)}']"
            return f"[name='{escape_attr(name)}']"

        # 3. Compound selector: data-testid + other distinguishing attributes
        testid = attrs.get('data-testid', '')
        placeholder = attrs.get('placeholder', '')
        input_type = attrs.get('type', '')
        aria_label = attrs.get('aria-label', '')

        if testid:
            # Try to make it unique with additional attributes
            if placeholder:
                return f"[data-testid='{escape_attr(testid)}'][placeholder='{escape_attr(placeholder)}']"
            if aria_label:
                return f"[data-testid='{escape_attr(testid)}'][aria-label='{escape_attr(aria_label)}']"
            if input_type and tag == 'input':
                return f"input[data-testid='{escape_attr(testid)}'][type='{escape_attr(input_type)}']"
            # data-testid alone might match multiple, but it's still useful
            return f"[data-testid='{escape_attr(testid)}']"

        # 4. placeholder (for inputs) - often unique
        if placeholder:
            if tag:
                return f"{tag}[placeholder='{escape_attr(placeholder)}']"
            return f"[placeholder='{escape_attr(placeholder)}']"

        # 5. aria-label (accessibility)
        if aria_label:
            if tag:
                return f"{tag}[aria-label='{escape_attr(aria_label)}']"
            return f"[aria-label='{escape_attr(aria_label)}']"

        # 6. Text content or title for buttons/links
        text = attrs.get('text', '').strip()
        title = attrs.get('title', '').strip()
        if tag in ['button', 'a', 'span']:
            # For buttons, prefer title attribute (more stable than inner text)
            if title:
                return f"{tag}[title='{escape_attr(title)}']"
            if text:
                safe_text = escape_attr(text[:50])
                return f"{tag}:has-text('{safe_text}')"

        # 7. role - but MUST combine with text/title to avoid generic selectors
        role = attrs.get('role', '')
        if role:
            # Role alone is TOO GENERIC (e.g., [role='menuitem'] matches all menu items)
            # Must combine with text or title
            if text:
                safe_text = escape_attr(text[:50])
                return f"[role='{escape_attr(role)}']:has-text('{safe_text}')"
            if title:
                return f"[role='{escape_attr(role)}'][title='{escape_attr(title)}']"
            if aria_label:
                return f"[role='{escape_attr(role)}'][aria-label='{escape_attr(aria_label)}']"
            # Don't return role alone - it's too generic, fall through to other options

        # 8. type alone - but only for specific input types, not generic button[type='button']
        if input_type and tag:
            # Avoid generic button[type='button'] - matches everything
            if tag == 'button' and input_type == 'button':
                # Need text content for buttons
                if text:
                    safe_text = escape_attr(text[:50])
                    return f"button:has-text('{safe_text}')"
                if title:
                    return f"button[title='{escape_attr(title)}']"
                # Don't return generic button[type='button'], fall through
            elif tag == 'input':
                # input[type='text'], input[type='email'] etc. are more specific
                return f"{tag}[type='{escape_attr(input_type)}']"

        # 9. XPath as fallback - most reliable but verbose
        if selector_info.get('xpath'):
            return f"xpath={selector_info['xpath']}"

        # 10. Index fallback (last resort)
        return f"[data-index='{fallback_index}']" if fallback_index else None

    async def _capture_action(self, action_type: str, selector: str = None, value: str = None):
        """Capture and emit an action."""
        await self._capture_action_with_selector(action_type, selector, value, {})

    async def _capture_action_with_selector(self, action_type: str, selector: str = None, value: str = None, selector_info: dict = None, assertion_config: dict = None):
        """Capture and emit an action with full selector info."""
        if not self.on_action:
            return

        screenshot = None
        try:
            if self.browser_session:
                screenshot_data = await self.browser_session.take_screenshot()
                if isinstance(screenshot_data, bytes):
                    screenshot = base64.b64encode(screenshot_data).decode('utf-8')
                else:
                    screenshot = screenshot_data
        except Exception:
            pass

        action = {
            "type": action_type,
            "selector": selector,
            "value": value,
            "screenshot": screenshot,
            "timestamp": datetime.utcnow().isoformat(),
            "selector_info": selector_info or {},  # Full info for Playwright generation
            "assertion_config": assertion_config,  # For assertion steps
        }
        await self.on_action(action)

    def _parse_assertion_request(self, task: str) -> Optional[Tuple[str, str, str]]:
        """
        Parse task for assertion language.
        Returns (assertion_type, target, expected_value) or None if not an assertion.
        """
        task_lower = task.lower().strip()

        for pattern, assertion_type in ASSERTION_PATTERNS:
            match = re.search(pattern, task_lower, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    # For value/attribute assertions: (target_element, expected_value)
                    target = groups[0].strip()
                    expected = groups[1].strip()
                else:
                    # For text/url/visibility: single capture
                    target = groups[0].strip()
                    expected = target
                print(f"[Agent] Detected assertion: type={assertion_type}, target='{target}', expected='{expected}'")
                return (assertion_type, target, expected)

        return None

    def _parse_hover_request(self, task: str) -> Optional[str]:
        """
        Parse task for hover requests.
        Returns the target element description or None if not a hover request.
        """
        task_lower = task.lower().strip()

        hover_patterns = [
            r'hover\s+(?:over\s+)?(?:the\s+)?(?:on\s+)?["\']?(.+?)["\']?\s*$',
            r'hover\s+(?:over\s+)?(?:the\s+)?(.+?)(?:\s+icon|\s+button|\s+element|\s+menu)?$',
            r'mouse\s*over\s+(?:the\s+)?["\']?(.+?)["\']?\s*$',
        ]

        for pattern in hover_patterns:
            match = re.search(pattern, task_lower, re.IGNORECASE)
            if match:
                target = match.group(1).strip()
                print(f"[Agent] Detected hover request for: '{target}'")
                return target

        return None

    async def _handle_hover(self, target: str) -> dict:
        """
        Handle hover request using Playwright directly.
        Works with iframes by searching all frames.
        """
        if not self.browser_session:
            return {"success": False, "message": "No browser session"}

        try:
            page = await self.browser_session.get_current_page()
            if not page:
                return {"success": False, "message": "No page available"}

            # Get the underlying Playwright page
            playwright_page = page._page if hasattr(page, '_page') else page

            # Build possible selectors for the target
            target_lower = target.lower()
            selectors_to_try = []

            # Common patterns for settings/gear icons
            if 'setting' in target_lower or 'gear' in target_lower or 'cog' in target_lower:
                selectors_to_try.extend([
                    '[aria-label*="setting" i]',
                    '[aria-label*="Settings" i]',
                    '[title*="setting" i]',
                    '[title*="Settings" i]',
                    'button[name*="Action"]',
                    'button[name*="action"]',
                    '[data-testid*="setting" i]',
                    '.settings-icon',
                    '.gear-icon',
                    'svg[class*="gear"]',
                    'button:has(svg)',
                ])

            # Generic selectors based on target text
            selectors_to_try.extend([
                f'[aria-label*="{target}" i]',
                f'[title*="{target}" i]',
                f'button:has-text("{target}")',
                f'a:has-text("{target}")',
                f'[data-testid*="{target}" i]',
                f'text="{target}"',
            ])

            # Try each selector in main frame first, then iframes
            all_frames = [playwright_page] + list(playwright_page.frames)

            for frame in all_frames:
                for selector in selectors_to_try:
                    try:
                        locator = frame.locator(selector)
                        count = await locator.count()
                        if count > 0:
                            # Use first visible element
                            for i in range(min(count, 5)):
                                elem = locator.nth(i)
                                if await elem.is_visible():
                                    await elem.hover(timeout=5000)

                                    # Capture the hover action
                                    await self._capture_action_with_selector(
                                        "hover",
                                        selector=selector,
                                        value=None,
                                        selector_info={'selector': selector}
                                    )

                                    frame_info = f" (in iframe: {frame.url[:50]})" if frame != playwright_page else ""
                                    print(f"[Agent] Hovered over '{selector}'{frame_info}")
                                    return {
                                        "success": True,
                                        "message": f"Hovered over {target} using selector: {selector}{frame_info}"
                                    }
                    except Exception as e:
                        continue

            # If we couldn't find by selectors, try using browser-use's DOM state
            try:
                dom_state = await self.browser_session.get_state()
                if dom_state and hasattr(dom_state, 'selector_map'):
                    for idx, elem in dom_state.selector_map.items():
                        attrs = elem.attributes if hasattr(elem, 'attributes') else {}
                        text = attrs.get('text', '') or attrs.get('aria-label', '') or attrs.get('title', '')
                        if target_lower in text.lower():
                            # Found element, try to hover using its xpath
                            if hasattr(elem, 'xpath') and elem.xpath:
                                for frame in all_frames:
                                    try:
                                        await frame.locator(f"xpath={elem.xpath}").hover(timeout=5000)
                                        await self._capture_action_with_selector(
                                            "hover",
                                            selector=f"xpath={elem.xpath}",
                                            value=None,
                                            selector_info={'xpath': elem.xpath}
                                        )
                                        print(f"[Agent] Hovered over element {idx} via xpath")
                                        return {"success": True, "message": f"Hovered over {target}"}
                                    except:
                                        continue
            except Exception as e:
                print(f"[Agent] DOM state hover fallback failed: {e}")

            return {"success": False, "message": f"Could not find element to hover: {target}"}

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    async def _handle_assertion(self, assertion_type: str, target: str, expected: str) -> dict:
        """
        Handle an assertion request by checking the current page state.
        """
        try:
            if not self.browser_session:
                return {"success": False, "message": "No browser session"}

            page = await self.browser_session.get_current_page()
            if not page:
                return {"success": False, "message": "No page available"}

            selector = None
            assertion_config = {}

            if assertion_type == 'assert_url':
                # URL assertion - no selector needed
                assertion_config = {
                    "expected": expected,
                    "operator": "contains"
                }
                await self._capture_action_with_selector(
                    assertion_type,
                    selector=None,
                    value=None,
                    assertion_config=assertion_config
                )
                print(f"[Agent] Added URL assertion: URL contains '{expected}'")
                return {"success": True, "message": f"Added check: URL contains '{expected}'"}

            elif assertion_type == 'assert_text':
                # Find element containing the text
                try:
                    locator = page.locator(f"text='{expected}'").first
                    if await locator.count() > 0:
                        selector = f"text='{expected}'"
                    else:
                        # Try body contains
                        selector = "body"
                except Exception:
                    selector = "body"

                assertion_config = {
                    "expected": expected,
                    "operator": "contains"
                }
                await self._capture_action_with_selector(
                    assertion_type,
                    selector=selector,
                    value=None,
                    assertion_config=assertion_config
                )
                print(f"[Agent] Added text assertion: '{expected}'")
                return {"success": True, "message": f"Added check: page contains '{expected}'"}

            elif assertion_type == 'assert_visible':
                # Try to find an element matching the description
                selector = await self._find_element_by_description(page, target)
                if selector:
                    await self._capture_action_with_selector(
                        assertion_type,
                        selector=selector,
                        value=None,
                        assertion_config={}
                    )
                    print(f"[Agent] Added visibility assertion: '{selector}'")
                    return {"success": True, "message": f"Added check: '{target}' is visible"}
                else:
                    return {"success": False, "message": f"Could not find element: {target}"}

            elif assertion_type == 'assert_hidden':
                selector = await self._find_element_by_description(page, target)
                if selector:
                    await self._capture_action_with_selector(
                        assertion_type,
                        selector=selector,
                        value=None,
                        assertion_config={}
                    )
                    print(f"[Agent] Added hidden assertion: '{selector}'")
                    return {"success": True, "message": f"Added check: '{target}' is hidden"}
                else:
                    # For hidden assertions, if we can't find the element, that's actually success
                    return {"success": True, "message": f"Added check: '{target}' is hidden (not found)"}

            elif assertion_type == 'assert_value':
                # Find input element and check its value
                selector = await self._find_element_by_description(page, target)
                if selector:
                    assertion_config = {
                        "expected": expected,
                        "operator": "equals"
                    }
                    await self._capture_action_with_selector(
                        assertion_type,
                        selector=selector,
                        value=None,
                        assertion_config=assertion_config
                    )
                    print(f"[Agent] Added value assertion: '{selector}' = '{expected}'")
                    return {"success": True, "message": f"Added check: '{target}' has value '{expected}'"}
                else:
                    return {"success": False, "message": f"Could not find element: {target}"}

            return {"success": True, "message": f"Added assertion check"}

        except Exception as e:
            print(f"[Agent] Assertion error: {e}")
            return {"success": False, "message": str(e)}

    async def _find_element_by_description(self, page, description: str) -> Optional[str]:
        """Try to find an element matching a natural language description."""
        description_lower = description.lower()

        # Common element patterns
        patterns = [
            # Buttons
            (r'(?:the\s+)?(\w+)\s+button', lambda m: f"button:has-text('{m.group(1)}')"),
            (r'button\s+(?:labeled|named|called)\s+["\']?(\w+)["\']?', lambda m: f"button:has-text('{m.group(1)}')"),
            # Links
            (r'(?:the\s+)?(\w+)\s+link', lambda m: f"a:has-text('{m.group(1)}')"),
            # Inputs
            (r'(?:the\s+)?(\w+)\s+(?:input|field)', lambda m: f"input[name='{m.group(1)}'], input[placeholder*='{m.group(1)}']"),
            # Generic text
            (r'["\'](.+?)["\']', lambda m: f"text='{m.group(1)}'"),
        ]

        for pattern, selector_fn in patterns:
            match = re.search(pattern, description_lower, re.IGNORECASE)
            if match:
                selector = selector_fn(match)
                try:
                    if await page.locator(selector).count() > 0:
                        return selector
                except Exception:
                    pass

        # Fallback: try as text selector
        try:
            text_selector = f"text='{description}'"
            if await page.locator(text_selector).count() > 0:
                return text_selector
        except Exception:
            pass

        return None

    async def _auto_add_assertions(self, result_message: str) -> list:
        """
        Automatically add assertions based on task completion.
        Analyzes URL changes and success indicators in the result.
        """
        print(f"[Auto-Assert] Starting auto-assertions, result_message: {result_message[:100] if result_message else 'None'}...")
        added_assertions = []

        if not self.browser_session:
            print("[Auto-Assert] No browser session, skipping")
            return added_assertions

        try:
            page = await self.browser_session.get_current_page()
            if not page:
                print("[Auto-Assert] No page available, skipping")
                return added_assertions

            # browser-use Page wrapper - use its methods
            current_url = await page.get_url() if hasattr(page, 'get_url') else None
            print(f"[Auto-Assert] initial_url={self.initial_url}, current_url={current_url}, page_type={type(page)}")

            if not current_url:
                print("[Auto-Assert] Could not get current URL, skipping URL assertion")

            # 1. URL changed significantly (different path) → add assert_url
            if self.initial_url and current_url:
                from urllib.parse import urlparse
                initial_parsed = urlparse(self.initial_url)
                current_parsed = urlparse(current_url)

                if initial_parsed.path != current_parsed.path:
                    path_segment = current_parsed.path.strip('/')
                    if path_segment:
                        assertion_config = {
                            "expected": f"/{path_segment.split('/')[0]}",  # First path segment
                            "operator": "contains"
                        }
                        await self._capture_action_with_selector(
                            "assert_url",
                            selector=None,
                            value=None,
                            assertion_config=assertion_config
                        )
                        added_assertions.append(f"URL contains '/{path_segment.split('/')[0]}'")
                        print(f"[Auto-Assert] Added URL assertion: {assertion_config['expected']}")

            # 2. Extract OBSERVED text from agent's response (not entered text)
            # Pattern: "displays 'X'", "shows 'X'", "message 'X'", "'X' appeared"
            # NOT: "entered 'X'", "typed 'X'", "credentials 'X'"

            # Find text that agent SAW (observation patterns)
            observation_patterns = [
                r"(?:displays?|shows?|showing|see|saw|found|appeared?|message|notification|text)\s+['\"]([^'\"]{3,50})['\"]",
                r"['\"]([^'\"]{3,50})['\"]\s+(?:appeared|displayed|shown|visible|message|notification)",
            ]

            for pattern in observation_patterns:
                matches = re.findall(pattern, result_message, re.IGNORECASE)
                for text in matches:
                    text = text.strip()
                    # Skip if it looks like credentials or input data
                    if '@' in text or text.isdigit() or len(text) < 4:
                        continue

                    assertion_config = {
                        "expected": text,
                        "operator": "contains"
                    }
                    await self._capture_action_with_selector(
                        "assert_text",
                        selector="body",
                        value=None,
                        assertion_config=assertion_config
                    )
                    added_assertions.append(f"page contains '{text}'")
                    print(f"[Auto-Assert] Added text assertion: '{text}'")
                    break
                if len(added_assertions) > 1:  # Already have URL + text
                    break

        except Exception as e:
            print(f"[Auto-Assert] Error: {e}")

        return added_assertions

    async def run(self, task: str, start_url: str = None) -> dict:
        """
        Run browser automation for the given task.
        Reuses browser session if already running.
        Supports natural language assertion requests.
        Auto-adds assertions on task completion.
        """
        assertion_request = self._parse_assertion_request(task)
        if assertion_request and self.browser_session:
            assertion_type, target, expected = assertion_request
            return await self._handle_assertion(assertion_type, target, expected)

        # Handle hover requests directly (bypasses agent since Gemini doesn't support custom actions)
        hover_target = self._parse_hover_request(task)
        if hover_target and self.browser_session:
            return await self._handle_hover(hover_target)

        try:
            from browser_use import Agent, Controller
            from browser_use.browser import BrowserSession

            # Select LLM based on config - custom actions only work with OpenAI/Anthropic
            provider = settings.browser_use_llm_provider.lower()
            if provider == "openai" and settings.openai_api_key:
                from langchain_openai import ChatOpenAI
                model = settings.browser_use_model or settings.openai_model
                llm = ChatOpenAI(model=model, api_key=settings.openai_api_key)
                print(f"[Agent] Using OpenAI: {model} (custom actions supported)")
            elif provider == "anthropic" and settings.anthropic_api_key:
                from langchain_anthropic import ChatAnthropic
                model = settings.browser_use_model or settings.anthropic_model
                llm = ChatAnthropic(model=model, api_key=settings.anthropic_api_key)
                print(f"[Agent] Using Anthropic: {model} (custom actions supported)")
            else:
                from browser_use.llm import ChatGoogle
                model = settings.browser_use_model or settings.gemini_model
                llm = ChatGoogle(model=model)
                print(f"[Agent] Using Gemini: {model} (WARNING: custom actions like hover may not work)")

            # Create controller with custom hover action
            controller = Controller()

            @controller.action("Hover over an element to reveal dropdowns, tooltips, or menus")
            async def hover(index: int, browser: BrowserSession):
                """
                Hover over an element at the specified index.
                Use this for dropdown menus, tooltips, or any UI that appears on mouse hover.
                """
                page = await browser.get_current_page()
                dom_state = await browser.get_state()

                if dom_state and dom_state.selector_map and index in dom_state.selector_map:
                    element = dom_state.selector_map[index]
                    # Try to build a selector from element attributes
                    attrs = element.attributes if hasattr(element, 'attributes') else {}

                    # Priority: id > data-testid > other attributes > xpath
                    selector = None
                    if attrs.get('id'):
                        selector = f"#{attrs['id']}"
                    elif attrs.get('data-testid'):
                        selector = f"[data-testid='{attrs['data-testid']}']"
                    elif attrs.get('aria-label'):
                        selector = f"[aria-label='{attrs['aria-label']}']"
                    elif hasattr(element, 'xpath') and element.xpath:
                        selector = f"xpath={element.xpath}"

                    if selector:
                        await page.locator(selector).hover(timeout=10000)
                        return f"Hovered over element {index} using selector: {selector}"

                # Fallback: use CDP to hover by backend node id
                try:
                    cdp = await page.context.new_cdp_session(page)
                    # Get the center point of the element
                    box_model = await cdp.send("DOM.getBoxModel", {"backendNodeId": index})
                    if box_model and "model" in box_model:
                        content = box_model["model"]["content"]
                        # content is [x1,y1, x2,y1, x2,y2, x1,y2]
                        center_x = (content[0] + content[2]) / 2
                        center_y = (content[1] + content[5]) / 2
                        await page.mouse.move(center_x, center_y)
                        return f"Hovered over element {index} at ({center_x}, {center_y})"
                except Exception as e:
                    print(f"[Hover] CDP fallback failed: {e}")

                return f"Could not hover over element {index}"

            if self.browser_session is None:
                print("[Agent] Creating new persistent browser session")
                self.browser_session = BrowserSession(
                    headless=True,
                    keep_alive=True,  # Keep browser alive between tasks
                )
                await self.browser_session.start()

                try:
                    page = await self.browser_session.get_current_page()
                    if page:
                        async def handle_dialog(dialog):
                            print(f"[Agent] Dialog captured: {dialog.type} - {dialog.message}")
                            # Report dialog as an action
                            if self.on_action:
                                await self.on_action({
                                    "type": "dialog",
                                    "value": dialog.message,
                                    "selector": dialog.type,  # alert/confirm/prompt
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                            await dialog.accept()
                        page.on('dialog', lambda d: asyncio.create_task(handle_dialog(d)))
                except Exception as e:
                    print(f"[Agent] Warning: Could not set up dialog handler: {e}")

                self.running = True
                self.screenshot_task = asyncio.create_task(self._stream_screenshots())

                # Include URL in task if provided
                full_task = task
                if start_url:
                    full_task = f"First navigate to {start_url}, then: {task}"
            else:
                print("[Agent] Reusing existing browser session")
                # Just the task, no URL needed - we're already on the page
                full_task = task

            # Callback to capture each step/action with proper selectors
            def on_step(browser_state, agent_output, step_num):
                try:
                    if agent_output and hasattr(agent_output, 'action'):
                        for action_model in agent_output.action:
                            if hasattr(action_model, 'root'):
                                inner = action_model.root

                                action_data = None
                                action_type = None
                                for attr in ['click', 'input', 'navigate', 'wait', 'done', 'scroll', 'hover']:
                                    if hasattr(inner, attr):
                                        action_data = getattr(inner, attr)
                                        action_type = attr
                                        break

                                if action_data and action_type:
                                    index = getattr(action_data, 'index', None)
                                    value = getattr(action_data, 'text', None) or getattr(action_data, 'url', None)

                                    # Try to get real selector from browser state
                                    selector_info = {}
                                    if index is not None and browser_state:
                                        try:
                                            # BrowserStateSummary has dom_state: SerializedDOMState
                                            # SerializedDOMState has selector_map: dict[int, EnhancedDOMTreeNode]
                                            dom_state = getattr(browser_state, 'dom_state', None)
                                            if dom_state:
                                                selector_map = getattr(dom_state, 'selector_map', None)
                                                if selector_map and index in selector_map:
                                                    elem = selector_map[index]
                                                    # EnhancedDOMTreeNode has:
                                                    # - attributes: dict[str, str]
                                                    # - node_name: str (tag name)
                                                    # - xpath: str property
                                                    attrs = elem.attributes if hasattr(elem, 'attributes') else {}
                                                    if not isinstance(attrs, dict):
                                                        attrs = dict(attrs) if attrs else {}

                                                    xpath = elem.xpath if hasattr(elem, 'xpath') else None
                                                    tag_name = elem.node_name if hasattr(elem, 'node_name') else None

                                                    text_content = None

                                                    if hasattr(elem, 'get_all_children_text'):
                                                        try:
                                                            text_content = elem.get_all_children_text()
                                                            if text_content:
                                                                text_content = str(text_content).strip()[:100]
                                                        except:
                                                            pass

                                                    if not text_content and hasattr(elem, 'get_meaningful_text_for_llm'):
                                                        try:
                                                            text_content = elem.get_meaningful_text_for_llm()
                                                            if text_content:
                                                                text_content = str(text_content).strip()[:100]
                                                        except:
                                                            pass

                                                    # Fallback: check standard properties
                                                    if not text_content:
                                                        for text_attr in ['text', 'text_content', 'inner_text', 'textContent']:
                                                            if hasattr(elem, text_attr):
                                                                val = getattr(elem, text_attr, None)
                                                                if val:
                                                                    text_content = str(val).strip()[:100]
                                                                    break

                                                    # Also check if text is in attributes
                                                    if not text_content:
                                                        text_content = attrs.get('text', '') or attrs.get('innerText', '')

                                                    if text_content:
                                                        attrs['text'] = text_content

                                                    selector_info = {
                                                        'xpath': xpath,
                                                        'attributes': attrs,
                                                        'tag': tag_name,
                                                    }
                                                    # Log useful attributes for debugging
                                                    useful_attrs = {k: v for k, v in attrs.items()
                                                                    if k in ['id', 'name', 'data-testid', 'placeholder',
                                                                             'aria-label', 'type', 'role', 'title', 'class', 'text']}
                                                    print(f"[Step] Found selector: tag={tag_name}, attrs={useful_attrs}")
                                        except Exception as e:
                                            import traceback
                                            print(f"[Step] Selector extraction error: {e}")
                                            traceback.print_exc()

                                    type_map = {'input': 'fill', 'goto': 'navigate'}
                                    mapped_type = type_map.get(action_type, action_type)

                                    playwright_selector = self._build_selector(selector_info, index)

                                    print(f"[Step] Captured: {mapped_type}, selector={playwright_selector}, value={value}")
                                    asyncio.create_task(self._capture_action_with_selector(
                                        mapped_type,
                                        selector=playwright_selector,
                                        value=value,
                                        selector_info=selector_info
                                    ))
                except Exception as e:
                    import traceback
                    print(f"[Step] Error: {e}")
                    traceback.print_exc()

            self.agent = Agent(
                task=full_task,
                llm=llm,
                browser_session=self.browser_session,
                controller=controller,  # Custom controller with hover action
                use_judge=False,  # Skip verification step
                use_thinking=False,  # Skip thinking for faster response
                register_new_step_callback=on_step,
                max_history_items=10,  # Limit history to reduce token costs
            )

            # Capture initial navigate action if URL provided
            if start_url:
                await self._capture_action("navigate", value=start_url)
                self.initial_url = start_url
            else:
                # Track current URL as initial for this task
                try:
                    page = await self.browser_session.get_current_page()
                    if page:
                        self.initial_url = page.url
                except Exception:
                    pass

            print("[Agent] Starting agent.run()...")
            try:
                result = await self.agent.run()
                print(f"[Agent] agent.run() completed, result type: {type(result)}")
            except Exception as run_error:
                print(f"[Agent] agent.run() raised exception: {run_error}")
                import traceback
                traceback.print_exc()
                raise

            final_result = result.final_result() if hasattr(result, 'final_result') else None
            result_message = final_result if final_result else ""
            print(f"[Agent] final_result: {final_result[:100] if final_result else 'None'}...")

            # Log token usage for cost analysis
            # result is AgentHistoryList which has .usage directly
            print("\n" + "="*60)
            print("[TOKEN USAGE] End-to-end flow cost breakdown:")
            print("="*60)

            usage = getattr(result, 'usage', None)

            if usage:
                # browser-use uses total_prompt_tokens / total_completion_tokens
                input_tokens = getattr(usage, 'total_prompt_tokens', 0) or 0
                output_tokens = getattr(usage, 'total_completion_tokens', 0) or 0
                cached_tokens = getattr(usage, 'total_prompt_cached_tokens', 0) or 0
                total_tokens = getattr(usage, 'total_tokens', 0) or (input_tokens + output_tokens)
                num_invocations = getattr(usage, 'entry_count', 0) or 0

                # Gemini 2.5 Flash pricing (per 1M tokens)
                # Input: $0.15/1M, Output: $0.60/1M (under 128k context)
                input_cost = (input_tokens / 1_000_000) * 0.15
                output_cost = (output_tokens / 1_000_000) * 0.60
                total_cost = input_cost + output_cost

                print(f"  Input tokens:    {input_tokens:,}")
                print(f"  Output tokens:   {output_tokens:,}")
                print(f"  Cached tokens:   {cached_tokens:,}")
                print(f"  Total tokens:    {total_tokens:,}")
                print(f"  LLM calls:       {num_invocations}")
                print("-"*40)
                print(f"  Input cost:      ${input_cost:.4f}")
                print(f"  Output cost:     ${output_cost:.4f}")
                print(f"  TOTAL COST:      ${total_cost:.4f}")
                if num_invocations > 0:
                    print(f"  Avg cost/call:   ${total_cost/num_invocations:.4f}")
            else:
                print("  No usage data in result")
                # Try to get from agent's token_cost_service
                if self.agent and hasattr(self.agent, 'token_cost_service'):
                    try:
                        usage_summary = await self.agent.token_cost_service.get_usage_summary()
                        print(f"  From token_cost_service: {usage_summary}")
                    except Exception as e:
                        print(f"  Could not get from token_cost_service: {e}")
            print("="*60 + "\n")

            # Auto-add assertions based on success signals
            print("[Agent] Calling _auto_add_assertions...")
            added_assertions = await self._auto_add_assertions(result_message)
            print(f"[Agent] _auto_add_assertions returned: {added_assertions}")

            # Build response message
            if added_assertions:
                assertions_summary = ", ".join(added_assertions)
                message = f"{result_message}\n\nAuto-added checks: {assertions_summary}" if result_message else f"Added checks: {assertions_summary}"
            else:
                message = final_result if final_result else "Automation completed successfully"

            return {
                "success": True,
                "message": message
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": str(e)
            }

    async def stop(self):
        """Stop browser and cleanup."""
        self.running = False

        if self.screenshot_task:
            self.screenshot_task.cancel()
            try:
                await self.screenshot_task
            except asyncio.CancelledError:
                pass

        if self.browser_session:
            try:
                await self.browser_session.stop()
            except Exception:
                pass

        self.browser_session = None
        self.agent = None
