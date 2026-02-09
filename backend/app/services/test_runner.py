"""Run saved tests using Playwright with visual feedback and performance metrics."""

import asyncio
import base64
import re
from typing import Callable, Awaitable, List, Optional
from playwright.async_api import async_playwright, Page, Browser, Response

from app.config import get_settings

settings = get_settings()


class PlaywrightTestRunner:
    """Execute saved tests with Playwright, stream screenshots, and capture performance metrics."""

    def __init__(
        self,
        on_step: Callable[[dict], Awaitable[None]] = None,
        on_screenshot: Callable[[str], Awaitable[None]] = None,
        on_metrics: Callable[[dict], Awaitable[None]] = None,
        on_dialog: Callable[[dict], Awaitable[None]] = None,
        on_healing: Callable[[dict], Awaitable[None]] = None,
        on_approval_request: Callable[[dict], Awaitable[dict]] = None,
        enable_healing: bool = True,
        healer_config: dict = None,
    ):
        self.on_step = on_step
        self.on_screenshot = on_screenshot
        self.on_metrics = on_metrics
        self.on_dialog = on_dialog
        self.on_healing = on_healing
        self.on_approval_request = on_approval_request  # Callback to request and wait for approval
        self.healer_config = healer_config
        # Use config if provided, otherwise check env settings
        if healer_config:
            self.enable_healing = enable_healing and healer_config.get('enabled', True)
        else:
            self.enable_healing = enable_healing and settings.healing_enabled
        self.browser: Browser = None
        self.page: Page = None
        self.running = False
        self.screenshot_task = None
        # Network capture for API assertions
        self.captured_requests: List[dict] = []
        # Dialog/alert capture
        self.captured_dialogs: List[dict] = []
        # Healing suggestions collected during run
        self.healing_suggestions: List[dict] = []

    async def _stream_screenshots(self):
        """Stream screenshots at regular intervals."""
        while self.running and self.page:
            try:
                screenshot = await self.page.screenshot(type='jpeg', quality=70)
                if screenshot and self.on_screenshot:
                    screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
                    await self.on_screenshot(screenshot_b64)
                await asyncio.sleep(0.3)  # ~3 fps
            except Exception as e:
                print(f"[TestRunner] Screenshot error: {e}")
                await asyncio.sleep(0.5)

    async def _capture_performance_metrics(self, step_index: int, url: str) -> Optional[dict]:
        """Capture Core Web Vitals and performance metrics after navigation."""
        try:
            timing = await self.page.evaluate('''() => {
                const nav = performance.getEntriesByType('navigation')[0];
                if (!nav) return null;
                return {
                    dns: nav.domainLookupEnd - nav.domainLookupStart,
                    tcp: nav.connectEnd - nav.connectStart,
                    ttfb: nav.responseStart - nav.requestStart,
                    download: nav.responseEnd - nav.responseStart,
                    domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
                    load: nav.loadEventEnd - nav.startTime,
                };
            }''')

            paint = await self.page.evaluate('''() => {
                const entries = {};
                performance.getEntriesByType('paint').forEach(entry => {
                    entries[entry.name] = entry.startTime;
                });
                return entries;
            }''')

            lcp = await self.page.evaluate('''() => {
                return new Promise((resolve) => {
                    let lcpValue = 0;
                    const observer = new PerformanceObserver((list) => {
                        const entries = list.getEntries();
                        const lastEntry = entries[entries.length - 1];
                        lcpValue = lastEntry.startTime;
                    });
                    try {
                        observer.observe({ type: 'largest-contentful-paint', buffered: true });
                        setTimeout(() => {
                            observer.disconnect();
                            resolve(lcpValue);
                        }, 100);
                    } catch (e) {
                        resolve(0);
                    }
                });
            }''')

            cls = await self.page.evaluate('''() => {
                return new Promise((resolve) => {
                    let clsValue = 0;
                    const observer = new PerformanceObserver((list) => {
                        for (const entry of list.getEntries()) {
                            if (!entry.hadRecentInput) {
                                clsValue += entry.value;
                            }
                        }
                    });
                    try {
                        observer.observe({ type: 'layout-shift', buffered: true });
                        setTimeout(() => {
                            observer.disconnect();
                            resolve(clsValue);
                        }, 100);
                    } catch (e) {
                        resolve(0);
                    }
                });
            }''')

            metrics = {
                'step_index': step_index,
                'url': url,
                'ttfb': round(timing.get('ttfb', 0)) if timing else 0,
                'fcp': round(paint.get('first-contentful-paint', 0)) if paint else 0,
                'lcp': round(lcp) if lcp else 0,
                'dom_content_loaded': round(timing.get('domContentLoaded', 0)) if timing else 0,
                'load': round(timing.get('load', 0)) if timing else 0,
                'cls': round(cls * 1000) / 1000 if cls else 0,  # Round to 3 decimals
            }

            return metrics

        except Exception as e:
            print(f"[TestRunner] Metrics error: {e}")
            return None

    def _get_metric_rating(self, metric_name: str, value: float) -> str:
        """Get rating (good/needs-improvement/poor) based on Core Web Vitals thresholds."""
        thresholds = {
            'lcp': (2500, 4000),      # good < 2.5s, poor > 4s
            'fcp': (1800, 3000),      # good < 1.8s, poor > 3s
            'cls': (0.1, 0.25),       # good < 0.1, poor > 0.25
            'ttfb': (800, 1800),      # good < 800ms, poor > 1.8s
        }

        if metric_name not in thresholds:
            return 'neutral'

        good, poor = thresholds[metric_name]
        if value <= good:
            return 'good'
        elif value <= poor:
            return 'needs-improvement'
        else:
            return 'poor'

    async def _setup_dialog_handler(self):
        """Set up handler for browser dialogs (alert, confirm, prompt)."""
        async def handle_dialog(dialog):
            dialog_info = {
                'type': dialog.type,  # 'alert', 'confirm', 'prompt', 'beforeunload'
                'message': dialog.message,
                'default_value': dialog.default_value,
            }
            self.captured_dialogs.append(dialog_info)
            print(f"[TestRunner] Dialog captured: {dialog.type} - {dialog.message}")

            # Notify via callback
            if self.on_dialog:
                await self.on_dialog(dialog_info)

            # Auto-accept dialogs to continue automation
            await dialog.accept()

        self.page.on('dialog', lambda d: asyncio.create_task(handle_dialog(d)))

    async def _setup_network_capture(self):
        """Set up network request/response capture for API assertions."""
        async def on_response(response: Response):
            try:
                # Only capture API-like requests (JSON responses, XHR, etc.)
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type or 'api' in response.url or '/api/' in response.url:
                    body = None
                    try:
                        body = await response.text()
                    except:
                        pass

                    self.captured_requests.append({
                        'url': response.url,
                        'method': response.request.method,
                        'status': response.status,
                        'content_type': content_type,
                        'body': body[:5000] if body else None,  # Limit body size
                    })
            except Exception as e:
                print(f"[TestRunner] Network capture error: {e}")

        self.page.on('response', on_response)

    def _compare(self, actual: str, expected: str, operator: str) -> bool:
        """Compare values using the specified operator."""
        if actual is None:
            actual = ''
        if expected is None:
            expected = ''

        actual = str(actual)
        expected = str(expected)

        if operator == 'equals':
            return actual == expected
        elif operator == 'contains':
            return expected in actual
        elif operator == 'matches':
            try:
                return bool(re.match(expected, actual))
            except:
                return False
        elif operator == 'not_equals':
            return actual != expected
        elif operator == 'not_contains':
            return expected not in actual
        elif operator == 'gt':
            try:
                return float(actual) > float(expected)
            except:
                return False
        elif operator == 'lt':
            try:
                return float(actual) < float(expected)
            except:
                return False
        elif operator == 'gte':
            try:
                return float(actual) >= float(expected)
            except:
                return False
        elif operator == 'lte':
            try:
                return float(actual) <= float(expected)
            except:
                return False
        else:
            return actual == expected

    async def _execute_assertion(self, step: dict) -> tuple[bool, str, str]:
        """
        Execute an assertion step.

        Returns:
            tuple of (passed, message, actual_value)
        """
        step_type = step.get('type', '')
        selector = step.get('selector', '')
        config = step.get('assertion_config') or {}
        expected = config.get('expected', '')
        operator = config.get('operator', 'equals')

        print(f"[TestRunner] Executing assertion: type={step_type}, selector={selector}")
        print(f"[TestRunner] Config: {config}")
        print(f"[TestRunner] Expected: '{expected}', Operator: '{operator}'")

        try:
            if step_type == 'assert_visible':
                if not selector:
                    return False, "Selector required for assert_visible", ""
                locator = self.page.locator(selector)
                # Wait for element to appear (e.g., validation errors after form submit)
                try:
                    await locator.wait_for(state='visible', timeout=10000)
                    return True, "Element is visible", "true"
                except Exception:
                    is_visible = await locator.is_visible()
                    return is_visible, f"Element {'is' if is_visible else 'is not'} visible", str(is_visible)

            elif step_type == 'assert_hidden':
                if not selector:
                    return False, "Selector required for assert_hidden", ""
                locator = self.page.locator(selector)
                is_visible = await locator.is_visible()
                return not is_visible, f"Element {'is' if is_visible else 'is not'} visible", str(not is_visible)

            elif step_type == 'assert_text':
                if not selector:
                    return False, "Selector required for assert_text", ""

                # For body selector with contains operator, use smarter text search
                if selector == 'body' and operator == 'contains' and expected:
                    # Search in main frame first, then all iframes
                    all_frames = [self.page] + self.page.frames
                    for frame in all_frames:
                        try:
                            text_locator = frame.get_by_text(expected, exact=False)
                            await text_locator.first.wait_for(state='visible', timeout=3000)
                            return True, f"Found text containing '{expected}'", expected
                        except Exception:
                            continue

                    # Text not found in any frame
                    visible_text = await self.page.evaluate('() => document.body.innerText.substring(0, 200)')
                    return False, f"Text '{expected}' not found. Visible: '{visible_text[:80]}...'", visible_text

                # Standard text content check for other selectors
                locator = self.page.locator(selector)
                await locator.wait_for(state='attached', timeout=10000)
                actual = await locator.text_content() or ''
                actual = actual.strip()
                passed = self._compare(actual, expected, operator)
                return passed, f"Text '{actual[:100]}' {operator} '{expected[:100]}'", actual

            elif step_type == 'assert_value':
                if not selector:
                    return False, "Selector required for assert_value", ""
                locator = self.page.locator(selector)
                await locator.wait_for(state='attached', timeout=10000)
                actual = await locator.input_value()
                passed = self._compare(actual, expected, operator)
                return passed, f"Value '{actual}' {operator} '{expected}'", actual

            elif step_type == 'assert_attribute':
                if not selector:
                    return False, "Selector required for assert_attribute", ""
                attribute = config.get('attribute', '')
                if not attribute:
                    return False, "Attribute name required for assert_attribute", ""
                locator = self.page.locator(selector)
                await locator.wait_for(state='attached', timeout=10000)
                actual = await locator.get_attribute(attribute) or ''
                passed = self._compare(actual, expected, operator)
                return passed, f"Attribute '{attribute}' = '{actual}' {operator} '{expected}'", actual

            elif step_type == 'assert_url':
                # Fail early if no expected value configured
                if not expected:
                    actual = self.page.url
                    return False, f"URL assertion has no expected value configured (current: {actual})", actual

                # Wait for URL to match (with timeout) instead of immediate check
                try:
                    if operator == 'contains':
                        await self.page.wait_for_url(f"**{expected}**", timeout=10000)
                    elif operator == 'matches':
                        await self.page.wait_for_url(re.compile(expected), timeout=10000)
                    else:
                        await self.page.wait_for_url(expected, timeout=10000)
                    actual = self.page.url
                    return True, f"URL '{actual}' {operator} '{expected}'", actual
                except Exception as e:
                    actual = self.page.url
                    return False, f"URL '{actual}' {operator} '{expected}' (timeout)", actual

            elif step_type == 'assert_api':
                # Find matching API request
                api_method = config.get('api_method', '').upper()
                api_url_pattern = config.get('api_url_pattern', '')
                api_status = config.get('api_status')
                api_body_contains = config.get('api_body_contains', '')

                # Find matching request
                matching_request = None
                for req in reversed(self.captured_requests):  # Most recent first
                    url_matches = api_url_pattern in req['url'] if api_url_pattern else True
                    method_matches = req['method'] == api_method if api_method else True
                    if url_matches and method_matches:
                        matching_request = req
                        break

                if not matching_request:
                    return False, f"No API request found matching pattern '{api_url_pattern}'", ""

                if api_status is not None:
                    if matching_request['status'] != api_status:
                        return False, f"API status {matching_request['status']} != expected {api_status}", str(matching_request['status'])

                if api_body_contains:
                    body = matching_request.get('body', '') or ''
                    if api_body_contains not in body:
                        return False, f"API body does not contain '{api_body_contains}'", body[:200]

                return True, f"API {api_method or 'request'} to '{api_url_pattern}' returned {matching_request['status']}", str(matching_request['status'])

            elif step_type == 'assert_vision':
                # Vision-based assertion using Gemini to analyze screenshot
                expected_result = config.get('expected', '') or expected
                if not expected_result:
                    return False, "Expected result required for assert_vision", ""

                # Take screenshot
                screenshot = await self.page.screenshot(type='png')
                screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')

                # Use Gemini vision to analyze
                result = await self._analyze_screenshot_for_assertion(screenshot_b64, expected_result)
                return result

            else:
                return False, f"Unknown assertion type: {step_type}", ""

        except Exception as e:
            return False, f"Assertion error: {str(e)}", ""

    async def _analyze_screenshot_for_assertion(
        self, screenshot_b64: str, expected_result: str
    ) -> tuple[bool, str, str]:
        """Use Gemini vision to analyze if expected result is visible on page."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.google_api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')

            image_part = {
                "mime_type": "image/png",
                "data": screenshot_b64
            }

            prompt = f"""Analyze this screenshot and determine if the following expected result is visible:

EXPECTED: {expected_result}

Look for:
- Error messages, validation errors, warning text
- Red/orange colored text indicating errors
- Form validation feedback
- Any text that indicates the expected behavior occurred

Respond in this exact format:
RESULT: PASS or FAIL
REASON: Brief explanation of what you see (1 sentence)
"""

            response = model.generate_content([prompt, image_part])
            result_text = response.text.strip()

            print(f"[TestRunner] Vision assertion response: {result_text}")

            lines = result_text.split('\n')
            passed = False
            reason = "Could not parse vision response"

            for line in lines:
                if line.startswith('RESULT:'):
                    passed = 'PASS' in line.upper()
                elif line.startswith('REASON:'):
                    reason = line.replace('REASON:', '').strip()

            if passed:
                return True, f"Vision check passed: {reason}", expected_result
            else:
                return False, f"Vision check failed: {reason}", expected_result

        except Exception as e:
            print(f"[TestRunner] Vision assertion error: {e}")
            return False, f"Vision analysis error: {str(e)}", ""

    async def run(self, steps: List[dict], target_url: str = None) -> dict:
        """
        Run a test with the given steps.

        Args:
            steps: List of step dicts with type, selector, value
            target_url: Optional starting URL

        Returns:
            dict with success status and message
        """
        print(f"[TestRunner] Starting test with {len(steps)} steps")
        for i, s in enumerate(steps):
            print(f"[TestRunner] Step {i}: type={s.get('type')}, assertion_config={s.get('assertion_config')}")

        all_metrics = []

        try:
            async with async_playwright() as p:
                # Launch browser with stealth options to avoid bot detection
                self.browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                    ]
                )

                context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation'],
                    java_script_enabled=True,
                )

                self.page = await context.new_page()

                # Hide webdriver property to avoid detection
                await self.page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                    window.chrome = { runtime: {} };
                """)

                await self._setup_dialog_handler()
                await self._setup_network_capture()

                self.running = True
                self.screenshot_task = asyncio.create_task(self._stream_screenshots())

                for i, step in enumerate(steps):
                    step_type = step.get('type', '')
                    selector = step.get('selector', '')
                    value = step.get('value', '')

                    # Skip wait steps if followed by element-based assertions (they have built-in waits)
                    # But DON'T skip for URL/API assertions - those need the wait for navigation/network
                    if step_type == 'wait':
                        next_step = steps[i + 1] if i + 1 < len(steps) else None
                        if next_step:
                            next_type = next_step.get('type', '')
                            # Only skip for element assertions that have wait_for built in
                            element_assertions = ['assert_visible', 'assert_hidden', 'assert_text', 'assert_value', 'assert_attribute']
                            if next_type in element_assertions:
                                if self.on_step:
                                    await self.on_step({
                                        'index': i,
                                        'type': step_type,
                                        'status': 'skipped',
                                        'selector': selector,
                                        'value': value,
                                    })
                                continue  # Skip this wait

                    # Notify step start
                    if self.on_step:
                        await self.on_step({
                            'index': i,
                            'type': step_type,
                            'status': 'running',
                            'selector': selector,
                            'value': value,
                        })

                    try:
                        is_assertion = step_type.startswith('assert_')

                        if is_assertion:
                            passed, message, actual = await self._execute_assertion(step)

                            if passed:
                                # Notify step success
                                if self.on_step:
                                    await self.on_step({
                                        'index': i,
                                        'type': step_type,
                                        'status': 'passed',
                                        'selector': selector,
                                        'value': value,
                                        'assertion_result': {
                                            'passed': True,
                                            'message': message,
                                            'actual': actual,
                                        }
                                    })
                            else:
                                # Notify step failure
                                if self.on_step:
                                    await self.on_step({
                                        'index': i,
                                        'type': step_type,
                                        'status': 'failed',
                                        'error': message,
                                        'selector': selector,
                                        'value': value,
                                        'assertion_result': {
                                            'passed': False,
                                            'message': message,
                                            'actual': actual,
                                        }
                                    })
                                raise Exception(f"Assertion failed: {message}")
                        else:
                            await self._execute_step(step_type, selector, value)

                            # Capture performance metrics after navigation
                            if step_type == 'navigate' and value:
                                # Wait a bit for metrics to be available
                                await asyncio.sleep(0.5)
                                metrics = await self._capture_performance_metrics(i, value)
                                if metrics and self.on_metrics:
                                    metrics['ratings'] = {
                                        'lcp': self._get_metric_rating('lcp', metrics['lcp']),
                                        'fcp': self._get_metric_rating('fcp', metrics['fcp']),
                                        'cls': self._get_metric_rating('cls', metrics['cls']),
                                        'ttfb': self._get_metric_rating('ttfb', metrics['ttfb']),
                                    }
                                    all_metrics.append(metrics)
                                    await self.on_metrics(metrics)

                            # Small delay for visual feedback
                            await asyncio.sleep(0.3)

                            # Notify step success
                            if self.on_step:
                                await self.on_step({
                                    'index': i,
                                    'type': step_type,
                                    'status': 'passed',
                                    'selector': selector,
                                    'value': value,
                                })

                    except Exception as e:
                        error_msg = str(e)

                        # Attempt healing for selector-based failures
                        healed = False
                        if self.enable_healing and selector and not step_type.startswith('assert_'):
                            # Notify that we're attempting healing
                            if self.on_step:
                                await self.on_step({
                                    'index': i,
                                    'type': step_type,
                                    'status': 'healing',
                                    'error': error_msg,
                                    'selector': selector,
                                    'value': value,
                                })

                            # Try to heal
                            healing_result = await self._attempt_healing(step, error_msg, i)

                            if healing_result:
                                if healing_result.get('auto_approved'):
                                    # Auto-approved: retry with healed selector
                                    healed = await self._retry_with_healed_selector(
                                        step,
                                        healing_result['suggested_selector'],
                                        i,
                                    )
                                elif self.on_approval_request:
                                    # Wait for user approval
                                    if self.on_step:
                                        await self.on_step({
                                            'index': i,
                                            'type': step_type,
                                            'status': 'waiting_approval',
                                            'healing': healing_result,
                                            'selector': selector,
                                            'value': value,
                                        })

                                    # Request approval and wait for response
                                    approval = await self.on_approval_request(healing_result)

                                    if approval and approval.get('approved'):
                                        # User approved - retry with healed selector
                                        healed = await self._retry_with_healed_selector(
                                            step,
                                            healing_result['suggested_selector'],
                                            i,
                                        )
                                        if healed:
                                            # Mark as applied since it worked
                                            healing_result['user_approved'] = True

                        if healed:
                            # Healing succeeded, continue to next step
                            continue

                        # Notify step failure (if not already notified)
                        if self.on_step and not step_type.startswith('assert_'):
                            await self.on_step({
                                'index': i,
                                'type': step_type,
                                'status': 'failed',
                                'error': error_msg,
                                'selector': selector,
                                'value': value,
                            })
                        raise e

                # Capture final screenshot showing the end state
                await asyncio.sleep(0.5)  # Brief pause to ensure page is settled
                if self.on_screenshot and self.page:
                    try:
                        screenshot = await self.page.screenshot(type='jpeg', quality=70)
                        screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
                        await self.on_screenshot(screenshot_b64)
                    except Exception:
                        pass

                return {
                    'success': True,
                    'message': f'All {len(steps)} steps passed',
                    'metrics': all_metrics,
                    'healing_suggestions': self.healing_suggestions,
                }

        except Exception as e:
            # Capture final screenshot on failure too
            if self.on_screenshot and self.page:
                try:
                    screenshot = await self.page.screenshot(type='jpeg', quality=70)
                    screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
                    await self.on_screenshot(screenshot_b64)
                except Exception:
                    pass

            return {
                'success': False,
                'message': str(e),
                'metrics': all_metrics,
                'healing_suggestions': self.healing_suggestions,
            }
        finally:
            await self.stop()

    async def _get_frame_for_selector(self, selector: str):
        """Find the frame (main or iframe) that contains the selector."""
        # First check main frame
        if await self.page.locator(selector).count() > 0:
            return self.page

        # Check all iframes
        for frame in self.page.frames:
            if frame == self.page.main_frame:
                continue
            try:
                if await frame.locator(selector).count() > 0:
                    print(f"[TestRunner] Found selector '{selector}' in iframe: {frame.url[:80]}")
                    return frame
            except Exception:
                continue

        return self.page  # Default to main page

    async def _execute_step(self, step_type: str, selector: str, value: str):
        """Execute a single test step."""
        if step_type == 'navigate':
            await self.page.goto(value, wait_until='domcontentloaded', timeout=30000)
            try:
                await self.page.wait_for_function(
                    '''() => {
                        // Wait for at least one interactive element
                        const inputs = document.querySelectorAll('input, button, a');
                        return inputs.length > 3;  // Most pages have at least a few
                    }''',
                    timeout=15000
                )
            except Exception:
                # Fallback: just wait a bit for JS to render
                await self.page.wait_for_timeout(3000)

            # Wait for any iframes to load
            iframes = self.page.frames
            if len(iframes) > 1:
                print(f"[TestRunner] Found {len(iframes) - 1} iframe(s), waiting for them to load...")
                for frame in iframes:
                    if frame != self.page.main_frame:
                        try:
                            await frame.wait_for_load_state('domcontentloaded', timeout=10000)
                        except Exception:
                            pass

            # Log final URL after any redirects
            final_url = self.page.url
            print(f"[TestRunner] Navigate complete - Final URL: {final_url}")

        elif step_type == 'click':
            if selector:
                # Wait for page to be stable before looking for element
                try:
                    await self.page.wait_for_load_state('domcontentloaded', timeout=10000)
                except:
                    pass

                # Retry logic for elements that may appear after page transitions
                max_retries = 5
                last_error = None
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            print(f"[TestRunner] Click retry {attempt + 1}/{max_retries} for '{selector}'")
                            # Wait for network and page to settle
                            try:
                                await self.page.wait_for_load_state('networkidle', timeout=5000)
                            except:
                                pass
                            await asyncio.sleep(0.5)  # Extra settle time for animations

                        frame = await self._get_frame_for_selector(selector)
                        locator = frame.locator(selector)

                        count = await locator.count()
                        if count > 1:
                            print(f"[TestRunner] Selector '{selector}' matched {count} elements, trying to disambiguate...")
                            # Try visible only first
                            visible_locator = locator.locator('visible=true')
                            if await visible_locator.count() == 1:
                                locator = visible_locator
                            else:
                                # For buttons, prefer primary/submit buttons
                                for hint in ['[type="submit"]', '.primary', ':has-text("Continue")', ':has-text("Submit")', ':has-text("Login")', ':has-text("Sign")']:
                                    try:
                                        refined = frame.locator(f"{selector}{hint}")
                                        if await refined.count() == 1:
                                            print(f"[TestRunner] Refined to: {selector}{hint}")
                                            locator = refined
                                            break
                                    except:
                                        continue
                                else:
                                    # Last resort: use first match
                                    print(f"[TestRunner] Using first match for '{selector}'")
                                    locator = locator.first

                        # Wait for element to be visible and stable
                        await locator.wait_for(state='visible', timeout=10000)
                        await locator.click(timeout=10000)
                        break  # Success, exit retry loop

                    except Exception as e:
                        last_error = e
                        error_msg = str(e).lower()
                        # Retry if element is hidden or not yet visible (page transitions)
                        if attempt < max_retries - 1 and ('hidden' in error_msg or 'not visible' in error_msg or 'timeout' in error_msg):
                            print(f"[TestRunner] Element hidden/not visible, retrying after wait...")
                            await asyncio.sleep(1)  # Wait for animations
                            continue
                        raise last_error

                # Wait for any network activity and DOM changes to settle after click
                # This helps with AJAX-heavy apps where clicks trigger async updates
                try:
                    # First wait for network
                    await self.page.wait_for_load_state('networkidle', timeout=8000)
                except:
                    pass  # Don't fail if network doesn't idle

                # Extra wait for SPAs - allow DOM to update after network settles
                await asyncio.sleep(0.5)

                # If click was on a menu item or button that might open a modal/form, wait more
                if 'menu' in selector.lower() or 'add' in selector.lower() or 'new' in selector.lower():
                    print(f"[TestRunner] Detected possible modal trigger, waiting for DOM to settle...")
                    try:
                        await self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                        await asyncio.sleep(1)  # Extra time for modal animation
                    except:
                        pass

        elif step_type == 'fill':
            if selector and value:
                # Find correct frame for this selector
                frame = await self._get_frame_for_selector(selector)
                locator = frame.locator(selector)

                count = await locator.count()
                if count > 1:
                    print(f"[TestRunner] Selector '{selector}' matched {count} elements for fill, using first visible...")
                    # For inputs, just use the first visible one
                    locator = locator.first

                # Wait for page to be stable before looking for element
                try:
                    await self.page.wait_for_load_state('domcontentloaded', timeout=10000)
                except:
                    pass

                # Wait for element to be visible with retry logic
                # Some pages have multi-step forms where fields appear after AJAX
                max_retries = 4
                last_error = None
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            print(f"[TestRunner] Retry {attempt + 1}/{max_retries} for '{selector}'")
                            # Wait for network and page to settle
                            try:
                                await self.page.wait_for_load_state('networkidle', timeout=5000)
                            except:
                                pass
                            # Re-get locator in case page changed
                            frame = await self._get_frame_for_selector(selector)
                            locator = frame.locator(selector)

                        # First wait for element to exist in DOM (attached)
                        await locator.wait_for(state='attached', timeout=8000)
                        # Then wait for it to be visible
                        await locator.wait_for(state='visible', timeout=8000)
                        break  # Success, exit retry loop
                    except Exception as e:
                        last_error = e
                        if attempt < max_retries - 1:
                            await asyncio.sleep(3)  # Wait before retry
                        continue
                else:
                    # All retries failed - log debug info
                    e = last_error
                    # Debug: log current URL and page content
                    current_url = self.page.url
                    print(f"[TestRunner] Fill failed - Current URL: {current_url}")
                    print(f"[TestRunner] Looking for selector: {selector}")
                    count = await frame.locator(selector).count()
                    print(f"[TestRunner] Element count for '{selector}': {count}")
                    # List available input fields for debugging
                    inputs = await frame.evaluate('''() => {
                        return Array.from(document.querySelectorAll('input')).slice(0, 10).map(el => ({
                            id: el.id,
                            name: el.name,
                            type: el.type,
                            placeholder: el.placeholder
                        }));
                    }''')
                    print(f"[TestRunner] Available inputs in frame: {inputs}")
                    iframes = await self.page.evaluate('''() => {
                        return Array.from(document.querySelectorAll('iframe')).map(f => f.src || 'no-src');
                    }''')
                    print(f"[TestRunner] Iframes on page: {iframes}")
                    try:
                        await self.page.screenshot(path='/tmp/debug_screenshot.png')
                        print(f"[TestRunner] Debug screenshot saved to /tmp/debug_screenshot.png")
                    except:
                        pass
                    raise Exception(f"Element '{selector}' not visible. Current URL: {current_url}")
                await locator.fill(value, timeout=10000)

        elif step_type == 'wait':
            try:
                ms = int(float(value) * 1000) if value else 1000
            except:
                ms = 1000
            await self.page.wait_for_timeout(ms)

        elif step_type == 'scroll':
            if selector:
                await self.page.locator(selector).scroll_into_view_if_needed()
            else:
                await self.page.mouse.wheel(0, 300)

        elif step_type == 'hover':
            if selector:
                await self.page.locator(selector).hover(timeout=10000)

        elif step_type == 'assert':
            if selector:
                await self.page.locator(selector).wait_for(state='visible', timeout=10000)

    async def _attempt_healing(self, step: dict, error_message: str, step_index: int) -> Optional[dict]:
        """
        Attempt to heal a failed step using LLM.

        Returns healing suggestion dict if successful, None otherwise.
        """
        if not self.enable_healing or not self.page:
            return None

        try:
            from app.services.context_collector import ContextCollector
            from app.services.healer import Healer, HealerConfig

            # Collect context
            collector = ContextCollector(self.page)
            context = await collector.collect(
                failed_step=step,
                error_message=error_message,
            )

            healer_config = None
            if self.healer_config:
                healer_config = HealerConfig(
                    enabled=self.healer_config.get('enabled', True),
                    auto_approve=self.healer_config.get('auto_approve', True),
                    auto_approve_threshold=self.healer_config.get('auto_approve_threshold', 0.85),
                    mode=self.healer_config.get('mode', 'inline'),
                    provider=self.healer_config.get('provider', 'gemini'),
                )

            healer = Healer(config=healer_config)
            suggestion = await healer.suggest_fix(context, use_vision=True)

            if not suggestion or suggestion.confidence == 0:
                return None

            result = {
                'step_index': step_index,
                'original_selector': step.get('selector'),
                'suggested_selector': suggestion.suggested_selector,
                'confidence': suggestion.confidence,
                'reasoning': suggestion.reasoning,
                'alternative_selectors': suggestion.alternative_selectors,
                'auto_approved': healer.should_auto_approve(suggestion),
                'context': {
                    'url': context['page']['url'],
                    'error': error_message,
                },
            }

            # Store suggestion
            self.healing_suggestions.append(result)

            # Notify via callback
            if self.on_healing:
                await self.on_healing(result)

            return result

        except Exception as e:
            print(f"[TestRunner] Healing attempt failed: {e}")
            return None

    async def _retry_with_healed_selector(
        self,
        step: dict,
        healed_selector: str,
        step_index: int,
    ) -> bool:
        """
        Retry a step with a healed selector.

        Returns True if retry succeeded, False otherwise.
        """
        try:
            step_type = step.get('type', '')
            value = step.get('value', '')

            print(f"[TestRunner] Retrying step {step_index} with healed selector: {healed_selector}")

            await self._execute_step(step_type, healed_selector, value)

            # Mark retry success on the healing suggestion
            for suggestion in self.healing_suggestions:
                if suggestion.get('step_index') == step_index:
                    suggestion['retry_success'] = True
                    break

            # Notify success
            if self.on_step:
                await self.on_step({
                    'index': step_index,
                    'type': step_type,
                    'status': 'healed',
                    'selector': healed_selector,
                    'value': value,
                    'original_selector': step.get('selector'),
                })

            return True

        except Exception as e:
            print(f"[TestRunner] Healed retry also failed: {e}")
            return False

    async def stop(self):
        """Stop the test runner and cleanup."""
        self.running = False

        if self.screenshot_task:
            self.screenshot_task.cancel()
            try:
                await self.screenshot_task
            except asyncio.CancelledError:
                pass

        if self.browser:
            try:
                await self.browser.close()
            except:
                pass

        self.browser = None
        self.page = None
