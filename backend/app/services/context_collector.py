"""Collect page context for self-healing when a test step fails."""

from typing import Optional
from playwright.async_api import Page, Frame


class ContextCollector:
    """Capture DOM state, elements, and screenshots for LLM-based healing."""

    def __init__(self, page: Page):
        self.page = page

    async def collect(self, failed_step: dict, error_message: str) -> dict:
        """
        Collect comprehensive context when a step fails.

        Returns a dict with:
        - page info (url, title)
        - screenshot (base64)
        - available elements (inputs, buttons, links, etc.)
        - failed step details
        - error message
        """
        context = {
            "page": await self._get_page_info(),
            "screenshot_b64": await self._capture_screenshot(),
            "elements": await self._collect_elements(),
            "iframes": await self._collect_iframes(),
            "failed_step": failed_step,
            "error_message": error_message,
        }
        return context

    async def _get_page_info(self) -> dict:
        """Get basic page information."""
        return {
            "url": self.page.url,
            "title": await self.page.title(),
        }

    async def _capture_screenshot(self) -> Optional[str]:
        """Capture screenshot as base64."""
        import base64
        try:
            screenshot = await self.page.screenshot(type='jpeg', quality=80, full_page=False)
            return base64.b64encode(screenshot).decode('utf-8')
        except Exception as e:
            print(f"[ContextCollector] Screenshot error: {e}")
            return None

    async def _collect_elements(self) -> dict:
        """Collect all interactive elements from the page."""
        try:
            elements = await self.page.evaluate('''() => {
                const getSelector = (el) => {
                    // Build a reliable selector for the element
                    if (el.id) return `#${el.id}`;
                    if (el.getAttribute('data-testid')) return `[data-testid="${el.getAttribute('data-testid')}"]`;
                    if (el.getAttribute('data-cy')) return `[data-cy="${el.getAttribute('data-cy')}"]`;
                    if (el.name) return `${el.tagName.toLowerCase()}[name="${el.name}"]`;

                    // Build class-based selector
                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.trim().split(/\\s+/).filter(c => c && !c.includes(':'));
                        if (classes.length > 0) {
                            return `${el.tagName.toLowerCase()}.${classes.slice(0, 2).join('.')}`;
                        }
                    }

                    return el.tagName.toLowerCase();
                };

                const getElementInfo = (el) => ({
                    selector: getSelector(el),
                    tag: el.tagName.toLowerCase(),
                    id: el.id || null,
                    name: el.getAttribute('name'),
                    type: el.getAttribute('type'),
                    placeholder: el.getAttribute('placeholder'),
                    text: el.innerText?.slice(0, 100)?.trim() || null,
                    value: el.value || null,
                    classes: el.className && typeof el.className === 'string'
                        ? el.className.trim().split(/\\s+/).filter(c => c).slice(0, 5)
                        : [],
                    visible: el.offsetParent !== null,
                    role: el.getAttribute('role'),
                    ariaLabel: el.getAttribute('aria-label'),
                    dataTestId: el.getAttribute('data-testid'),
                    href: el.getAttribute('href'),
                });

                const inputs = Array.from(document.querySelectorAll('input, textarea, select'))
                    .slice(0, 30)
                    .map(getElementInfo);

                const buttons = Array.from(document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"]'))
                    .slice(0, 20)
                    .map(getElementInfo);

                const links = Array.from(document.querySelectorAll('a[href]'))
                    .slice(0, 20)
                    .map(getElementInfo);

                const clickables = Array.from(document.querySelectorAll('[onclick], [data-action], .clickable, .btn'))
                    .filter(el => !el.matches('button, a, input'))
                    .slice(0, 15)
                    .map(getElementInfo);

                const forms = Array.from(document.querySelectorAll('form'))
                    .slice(0, 5)
                    .map(form => ({
                        selector: getSelector(form),
                        id: form.id || null,
                        action: form.action,
                        method: form.method,
                        inputCount: form.querySelectorAll('input, textarea, select').length,
                    }));

                return { inputs, buttons, links, clickables, forms };
            }''')
            return elements
        except Exception as e:
            print(f"[ContextCollector] Element collection error: {e}")
            return {"inputs": [], "buttons": [], "links": [], "clickables": [], "forms": []}

    async def _collect_iframes(self) -> list:
        """Collect information about iframes on the page."""
        try:
            iframes = await self.page.evaluate('''() => {
                return Array.from(document.querySelectorAll('iframe')).map(frame => ({
                    src: frame.src || null,
                    id: frame.id || null,
                    name: frame.name || null,
                    visible: frame.offsetParent !== null,
                }));
            }''')
            return iframes
        except Exception as e:
            print(f"[ContextCollector] Iframe collection error: {e}")
            return []

    async def collect_for_frame(self, frame: Frame, failed_step: dict, error_message: str) -> dict:
        """Collect context from a specific frame (for iframe scenarios)."""
        try:
            elements = await frame.evaluate('''() => {
                const getSelector = (el) => {
                    if (el.id) return `#${el.id}`;
                    if (el.getAttribute('data-testid')) return `[data-testid="${el.getAttribute('data-testid')}"]`;
                    if (el.name) return `${el.tagName.toLowerCase()}[name="${el.name}"]`;
                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.trim().split(/\\s+/).filter(c => c);
                        if (classes.length > 0) return `${el.tagName.toLowerCase()}.${classes[0]}`;
                    }
                    return el.tagName.toLowerCase();
                };

                const getElementInfo = (el) => ({
                    selector: getSelector(el),
                    tag: el.tagName.toLowerCase(),
                    id: el.id || null,
                    name: el.getAttribute('name'),
                    type: el.getAttribute('type'),
                    placeholder: el.getAttribute('placeholder'),
                    text: el.innerText?.slice(0, 100)?.trim() || null,
                    classes: el.className?.split?.(/\\s+/)?.slice(0, 5) || [],
                    visible: el.offsetParent !== null,
                });

                return {
                    inputs: Array.from(document.querySelectorAll('input, textarea, select')).slice(0, 20).map(getElementInfo),
                    buttons: Array.from(document.querySelectorAll('button, [role="button"]')).slice(0, 15).map(getElementInfo),
                    links: Array.from(document.querySelectorAll('a[href]')).slice(0, 15).map(getElementInfo),
                };
            }''')

            return {
                "frame_url": frame.url,
                "elements": elements,
                "failed_step": failed_step,
                "error_message": error_message,
            }
        except Exception as e:
            print(f"[ContextCollector] Frame collection error: {e}")
            return {"frame_url": frame.url, "elements": {}, "failed_step": failed_step, "error_message": error_message}
