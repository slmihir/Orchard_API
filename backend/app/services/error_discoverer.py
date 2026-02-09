"""
Error Discoverer - Runs variants and discovers actual error messages using vision.

This runs each variant, takes a screenshot at the assertion point,
and uses Gemini vision to extract the actual error text.
"""

import base64
import asyncio
from playwright.async_api import async_playwright
import google.generativeai as genai
from app.config import get_settings

settings = get_settings()


class ErrorDiscoverer:
    """Runs variants and discovers actual error messages."""

    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    async def discover_errors(self, variants: list[dict], target_url: str) -> list[dict]:
        """
        Run each variant and discover the actual error message.

        Args:
            variants: List of variant dicts with steps
            target_url: The target URL for the test

        Returns:
            Variants with updated assertions containing real error text
        """
        updated_variants = []

        for variant in variants:
            try:
                discovered = await self._run_and_discover(variant, target_url)
                updated_variants.append(discovered)
            except Exception as e:
                print(f"[ErrorDiscoverer] Failed to discover error for {variant.get('name')}: {e}")
                # Keep original variant if discovery fails
                updated_variants.append(variant)

        return updated_variants

    async def _run_and_discover(self, variant: dict, target_url: str) -> dict:
        """Run a single variant and discover its error message."""
        steps = variant.get('steps', [])

        # Find where the assertion should be (last step if it's an assertion, otherwise end)
        assertion_index = len(steps)
        for i, step in enumerate(steps):
            if step.get('type', '').startswith('assert_'):
                assertion_index = i
                break

        # Steps to run (before the assertion)
        steps_to_run = steps[:assertion_index]

        print(f"[ErrorDiscoverer] Running variant '{variant.get('name')}' with {len(steps_to_run)} steps")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = await context.new_page()

            try:
                for step in steps_to_run:
                    await self._execute_step(page, step)

                # Wait a moment for any error to appear
                await asyncio.sleep(1)

                # Take screenshot
                screenshot = await page.screenshot(type='png')
                screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

                # Use vision to extract the actual error
                error_text = await self._extract_error_text(screenshot_b64, variant.get('expected_result', ''))

                print(f"[ErrorDiscoverer] Discovered error: '{error_text}'")

                return self._update_variant_assertion(variant, error_text, assertion_index)

            finally:
                await browser.close()

    async def _execute_step(self, page, step: dict):
        """Execute a single step."""
        step_type = step.get('type', '')
        selector = step.get('selector', '')
        value = step.get('value', '')

        if step_type == 'navigate':
            await page.goto(value, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(2)  # Wait for page to settle

        elif step_type == 'click':
            if selector:
                # Try main page first, then iframes
                try:
                    locator = page.locator(selector)
                    await locator.wait_for(state='visible', timeout=10000)
                    await locator.click()
                except:
                    # Try iframes
                    for frame in page.frames:
                        try:
                            locator = frame.locator(selector)
                            if await locator.count() > 0:
                                await locator.click()
                                break
                        except:
                            continue
                await asyncio.sleep(0.5)

        elif step_type == 'fill':
            if selector:
                # Try main page first, then iframes
                try:
                    locator = page.locator(selector)
                    await locator.wait_for(state='visible', timeout=10000)
                    await locator.fill(value or '')
                except:
                    # Try iframes
                    for frame in page.frames:
                        try:
                            locator = frame.locator(selector)
                            if await locator.count() > 0:
                                await locator.fill(value or '')
                                break
                        except:
                            continue

        elif step_type == 'wait':
            try:
                ms = int(float(value) * 1000) if value else 1000
            except:
                ms = 1000
            await asyncio.sleep(ms / 1000)

    async def _extract_error_text(self, screenshot_b64: str, expected_context: str) -> str:
        """Use Gemini vision to extract the actual error text from screenshot."""
        image_part = {
            "mime_type": "image/png",
            "data": screenshot_b64
        }

        prompt = f"""Look at this screenshot and find any error or validation message.

Context: This is a test expecting: {expected_context}

Extract the EXACT error message text shown on the page. Look for:
- Red text
- Error messages near form fields
- Validation warnings
- Alert messages

Respond with ONLY the error text, nothing else. If no error is visible, respond with "NO_ERROR_FOUND".

Example responses:
- "Please enter a valid email address"
- "Password is required"
- "Incorrect email or password"
"""

        response = self.model.generate_content([prompt, image_part])
        error_text = response.text.strip()

        # Clean up response
        if error_text.startswith('"') and error_text.endswith('"'):
            error_text = error_text[1:-1]

        return error_text

    def _update_variant_assertion(self, variant: dict, error_text: str, assertion_index: int) -> dict:
        """Update variant with a text-based assertion using discovered error."""
        import copy
        updated = copy.deepcopy(variant)

        if error_text and error_text != "NO_ERROR_FOUND":
            assertion_step = {
                "type": "assert_text",
                "selector": "body",
                "value": "",
                "assertion_config": {
                    "expected": error_text,
                    "operator": "contains"
                },
                "_variant_assertion": True,
                "_discovered_error": error_text,
            }

            steps = updated.get('steps', [])
            if assertion_index < len(steps) and steps[assertion_index].get('type', '').startswith('assert_'):
                steps[assertion_index] = assertion_step
            else:
                steps.append(assertion_step)

            updated['steps'] = steps
            updated['discovered_error'] = error_text
            updated['has_assertion'] = True

        return updated
