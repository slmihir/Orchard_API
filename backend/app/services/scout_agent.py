"""Scout Agent - Explores websites and discovers features for testing."""

import asyncio
import base64
import hashlib
import re
import uuid
from collections import deque
from datetime import datetime
from typing import Callable, Awaitable, Optional, List
from urllib.parse import urlparse, urljoin

from pydantic import BaseModel, Field
from sqlalchemy import select
from app.db.postgres import AsyncSessionLocal
from app.models.project import Project, DiscoveredPage, PageConnection
from app.config import get_settings

settings = get_settings()


class FormFieldAnalysis(BaseModel):
    """Analysis of a form field."""
    name: str = Field(description="Field name/id attribute")
    label: str = Field(default="", description="Human-readable label for the field")
    field_type: str = Field(description="Type: text, email, password, number, select, checkbox, radio, textarea, file, date, etc.")
    required: bool = Field(default=False, description="Whether the field is required")
    validation_rules: List[str] = Field(default_factory=list, description="Validation rules like 'min length 8', 'email format', 'must match password'")
    placeholder: str = Field(default="", description="Placeholder text")
    options: List[str] = Field(default_factory=list, description="For select/radio - available options")
    default_value: str = Field(default="", description="Default or pre-filled value")


class FormAnalysis(BaseModel):
    """Analysis of a form on the page."""
    form_name: str = Field(default="", description="Form name or purpose (e.g., 'Login Form', 'Create User Form')")
    form_purpose: str = Field(description="What this form does when submitted")
    submit_button_text: str = Field(default="Submit", description="Text on the submit button")
    fields: List[FormFieldAnalysis] = Field(default_factory=list, description="List of form fields")
    submission_method: str = Field(default="POST", description="HTTP method: GET or POST")
    expected_outcome: str = Field(default="", description="What happens on successful submission (redirect, message, etc.)")


class ActionAnalysis(BaseModel):
    """Analysis of an interactive action on the page."""
    action_text: str = Field(description="Button/link text")
    action_type: str = Field(description="Type: button, link, icon_button, dropdown_trigger, tab, modal_trigger")
    action_purpose: str = Field(description="What this action does")
    requires_confirmation: bool = Field(default=False, description="Whether action shows confirmation dialog")
    is_destructive: bool = Field(default=False, description="Whether action is destructive (delete, remove, etc.)")
    target_url: str = Field(default="", description="For links - where it navigates to")


class TableAnalysis(BaseModel):
    """Analysis of a data table on the page."""
    table_name: str = Field(default="", description="What data this table shows")
    columns: List[str] = Field(default_factory=list, description="Column headers")
    has_pagination: bool = Field(default=False, description="Whether table has pagination")
    has_sorting: bool = Field(default=False, description="Whether columns are sortable")
    has_filtering: bool = Field(default=False, description="Whether table has filters")
    row_actions: List[str] = Field(default_factory=list, description="Actions available per row (edit, delete, view, etc.)")


class PageAnalysis(BaseModel):
    """Comprehensive LLM-generated analysis of a web page for test automation."""
    page_type: str = Field(
        description="Type of page: login, register, dashboard, list, detail, form, settings, landing, profile, search, checkout, error, modal, wizard, other"
    )
    page_description: str = Field(
        description="Brief description of what this page does (1-2 sentences)"
    )
    page_title: str = Field(default="", description="The visible title/heading of the page")

    # Features and capabilities
    features: List[str] = Field(
        default_factory=list,
        description="List of features/capabilities available on this page (e.g., 'User Login', 'Create Invoice', 'Search Products')"
    )

    # Authentication
    requires_auth: bool = Field(
        default=False,
        description="Whether this page requires authentication to access"
    )
    required_permissions: List[str] = Field(
        default_factory=list,
        description="Specific permissions needed (e.g., 'admin', 'editor', 'can_delete')"
    )

    # Forms - detailed analysis
    forms: List[FormAnalysis] = Field(
        default_factory=list,
        description="Detailed analysis of all forms on the page"
    )

    # Actions/Buttons
    actions: List[ActionAnalysis] = Field(
        default_factory=list,
        description="All interactive actions (buttons, links) on the page"
    )

    # Data tables
    tables: List[TableAnalysis] = Field(
        default_factory=list,
        description="Data tables on the page"
    )

    # Navigation
    navigation_items: List[str] = Field(
        default_factory=list,
        description="Main navigation links visible on this page"
    )
    breadcrumbs: List[str] = Field(
        default_factory=list,
        description="Breadcrumb trail if present"
    )

    # Error handling
    visible_errors: List[str] = Field(
        default_factory=list,
        description="Any error messages currently visible"
    )
    validation_messages: List[str] = Field(
        default_factory=list,
        description="Form validation messages visible"
    )

    # State
    loading_indicators: bool = Field(
        default=False,
        description="Whether page shows loading spinners/skeletons"
    )
    empty_state: bool = Field(
        default=False,
        description="Whether page shows empty state (no data)"
    )

    # Test suggestions
    suggested_test_scenarios: List[str] = Field(
        default_factory=list,
        description="Suggested test scenarios for this page (e.g., 'Test login with invalid credentials', 'Test form submission with empty required fields')"
    )


class ScoutAgent:
    """
    Explores a website systematically and discovers features.

    Uses BFS exploration with:
    - Depth limits
    - Page count limits
    - State deduplication
    - Pattern detection
    - Feature identification
    """

    def __init__(
        self,
        project_id: str,
        base_url: str,
        credentials: dict = None,
        max_depth: int = 5,
        max_pages: int = 100,
        # Callbacks for real-time updates
        on_page_discovered: Callable[[dict], Awaitable[None]] = None,
        on_connection_found: Callable[[dict], Awaitable[None]] = None,
        on_screenshot: Callable[[dict], Awaitable[None]] = None,
        on_activity: Callable[[dict], Awaitable[None]] = None,
        on_stats_update: Callable[[dict], Awaitable[None]] = None,
        on_section_found: Callable[[dict], Awaitable[None]] = None,
        on_feature_found: Callable[[dict], Awaitable[None]] = None,
        on_pattern_detected: Callable[[dict], Awaitable[None]] = None,
    ):
        self.project_id = project_id
        self.base_url = base_url
        self.credentials = credentials or {}
        self.max_depth = max_depth
        self.max_pages = max_pages

        # Callbacks
        self.on_page_discovered = on_page_discovered
        self.on_connection_found = on_connection_found
        self.on_screenshot = on_screenshot
        self.on_activity = on_activity
        self.on_stats_update = on_stats_update
        self.on_section_found = on_section_found
        self.on_feature_found = on_feature_found
        self.on_pattern_detected = on_pattern_detected

        # State
        self.browser_session = None
        self.running = False
        self.paused = False
        self.should_stop = False

        # Discovery state
        self.visited_states = set()  # Set of state hashes
        self.discovered_pages = {}  # url -> page_id
        self.patterns = {}  # pattern_id -> {count, representative_id}
        self.sections = set()

        # Stats
        self.stats = {
            "pages_discovered": 0,
            "features_found": 0,
            "patterns_detected": 0,
            "current_depth": 0,
        }

        # Queue for BFS: (url, depth, nav_steps, parent_page_id)
        self.queue = deque()

        # LLM for page analysis (initialized lazily)
        self._llm = None

    def _get_llm(self):
        """Get or create LLM instance for page analysis based on config."""
        if self._llm is None:
            try:
                provider = settings.browser_use_llm_provider.lower()

                if provider == "gemini":
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    model = settings.browser_use_model or settings.gemini_model or "gemini-2.0-flash-exp"
                    self._llm = ChatGoogleGenerativeAI(
                        model=model,
                        google_api_key=settings.google_api_key,
                        temperature=0,
                    )
                    print(f"[Scout] Using Gemini LLM: {model}")

                elif provider == "openai":
                    from langchain_openai import ChatOpenAI
                    model = settings.browser_use_model or settings.openai_model or "gpt-4o"
                    self._llm = ChatOpenAI(
                        model=model,
                        api_key=settings.openai_api_key,
                        temperature=0,
                    )
                    print(f"[Scout] Using OpenAI LLM: {model}")

                elif provider == "anthropic":
                    from langchain_anthropic import ChatAnthropic
                    model = settings.browser_use_model or settings.anthropic_model or "claude-sonnet-4-20250514"
                    self._llm = ChatAnthropic(
                        model=model,
                        api_key=settings.anthropic_api_key,
                        temperature=0,
                    )
                    print(f"[Scout] Using Anthropic LLM: {model}")

                else:
                    print(f"[Scout] Unknown LLM provider: {provider}, falling back to Gemini")
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    self._llm = ChatGoogleGenerativeAI(
                        model=settings.gemini_model or "gemini-2.0-flash-exp",
                        google_api_key=settings.google_api_key,
                        temperature=0,
                    )

            except Exception as e:
                print(f"[Scout] Failed to initialize LLM: {e}")
                return None
        return self._llm

    async def _analyze_page_with_llm(self, page, url: str) -> Optional[PageAnalysis]:
        """Use LLM to analyze the current page and extract structured information for test automation."""
        llm = self._get_llm()
        if not llm:
            return None

        try:
            html_content = ""
            try:
                html_content = await page.get_html()
                # Truncate if too long (keep first 15000 chars)
                if len(html_content) > 15000:
                    html_content = html_content[:15000] + "\n... [truncated]"
            except Exception:
                pass

            title = ""
            try:
                title = await page.get_title()
            except Exception:
                pass

            prompt = f"""Analyze this web page for TEST AUTOMATION purposes.

URL: {url}
Title: {title}

HTML Content:
```html
{html_content}
```

Provide a comprehensive JSON analysis with the following structure:
{{
  "page_type": "login|register|dashboard|list|detail|form|settings|landing|profile|search|checkout|error|modal|wizard|other",
  "page_description": "Brief description of what this page does",
  "page_title": "The visible title/heading",
  "features": ["List of features/capabilities on this page"],
  "requires_auth": true/false,
  "required_permissions": ["admin", "editor", etc.],
  "forms": [
    {{
      "form_name": "Login Form",
      "form_purpose": "Authenticate users",
      "submit_button_text": "Sign In",
      "fields": [
        {{
          "name": "email",
          "label": "Email Address",
          "field_type": "email",
          "required": true,
          "validation_rules": ["email format"],
          "placeholder": "Enter your email"
        }}
      ],
      "expected_outcome": "Redirects to dashboard on success"
    }}
  ],
  "actions": [
    {{
      "action_text": "Delete",
      "action_type": "button",
      "action_purpose": "Delete the item",
      "requires_confirmation": true,
      "is_destructive": true
    }}
  ],
  "tables": [
    {{
      "table_name": "Users List",
      "columns": ["Name", "Email", "Role"],
      "has_pagination": true,
      "has_sorting": true,
      "row_actions": ["edit", "delete"]
    }}
  ],
  "suggested_test_scenarios": [
    "Test login with valid credentials",
    "Test login with invalid password",
    "Test form validation for empty fields"
  ]
}}

Return ONLY valid JSON, no markdown or explanation."""

            # Call LLM with structured output
            structured_llm = llm.with_structured_output(PageAnalysis)
            analysis = await structured_llm.ainvoke(prompt)
            return analysis

        except Exception as e:
            print(f"[Scout] LLM analysis failed for {url}: {e}")
            return None

    def pause(self):
        """Pause exploration."""
        self.paused = True

    def resume(self):
        """Resume exploration."""
        self.paused = False

    def stop(self):
        """Stop exploration."""
        self.should_stop = True

    async def _emit_activity(self, message: str, activity_type: str = "info"):
        """Emit an activity log entry."""
        if self.on_activity:
            await self.on_activity({
                "message": message,
                "type": activity_type,
                "timestamp": datetime.utcnow().isoformat(),
            })

    async def _emit_stats(self):
        """Emit current stats."""
        if self.on_stats_update:
            await self.on_stats_update(self.stats)

    async def _take_screenshot(self) -> Optional[str]:
        """Take a screenshot and return base64 encoded image."""
        try:
            if self.browser_session:
                screenshot_data = await self.browser_session.take_screenshot()
                if isinstance(screenshot_data, bytes):
                    return base64.b64encode(screenshot_data).decode('utf-8')
                return screenshot_data
        except Exception:
            pass
        return None

    def _compute_state_hash(self, url: str, dom_markers: list) -> str:
        """Compute a hash representing the current page state."""
        # Combine URL path with key DOM markers for state identification
        parsed = urlparse(url)
        # Normalize path (remove trailing slashes, IDs)
        path = re.sub(r'/\d+(?=/|$)', '/:id', parsed.path.rstrip('/'))

        content = f"{parsed.netloc}{path}:{','.join(sorted(dom_markers[:10]))}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _detect_pattern(self, url: str, page_type: str) -> Optional[str]:
        """Detect if this page is part of a pattern (e.g., product/:id)."""
        parsed = urlparse(url)
        path = parsed.path

        # Common patterns
        patterns = [
            (r'/(\w+)/\d+$', lambda m: f"{m.group(1)}_detail"),  # /products/123
            (r'/(\w+)/\d+/(\w+)$', lambda m: f"{m.group(1)}_{m.group(2)}"),  # /users/123/orders
            (r'/(\w+)/\d+/edit$', lambda m: f"{m.group(1)}_edit"),  # /products/123/edit
            (r'/(\w+)/new$', lambda m: f"{m.group(1)}_new"),  # /products/new
        ]

        for pattern, extractor in patterns:
            match = re.search(pattern, path)
            if match:
                return extractor(match)

        return None

    def _extract_section(self, url: str, nav_path: list) -> Optional[str]:
        """Extract which section of the app this page belongs to."""
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')

        if path_parts and path_parts[0]:
            return path_parts[0]
        return None

    def _classify_page_type(self, forms: list, actions: list, url: str) -> str:
        """Classify the type of page based on its content."""
        path = urlparse(url).path.lower()

        # URL-based classification
        if 'login' in path or 'signin' in path:
            return 'login'
        if 'register' in path or 'signup' in path:
            return 'register'
        if 'dashboard' in path:
            return 'dashboard'
        if 'settings' in path:
            return 'settings'
        if '/new' in path or '/create' in path:
            return 'form_create'
        if '/edit' in path:
            return 'form_edit'

        # Content-based classification
        if forms:
            if len(forms) == 1:
                form = forms[0]
                fields = form.get('fields', [])
                if any('password' in f.get('name', '').lower() for f in fields):
                    return 'auth_form'
                return 'form'
            return 'multi_form'

        if actions:
            action_count = len(actions)
            if action_count > 10:
                return 'list'
            elif action_count > 5:
                return 'detail'

        return 'page'

    async def _extract_page_content(self, page) -> dict:
        """Extract forms, actions, and inputs from the current page."""
        forms = []
        actions = []
        inputs = []

        try:
            form_elements = await page.get_elements_by_css_selector('form')
            for form in form_elements:
                form_data = {
                    "action": await form.get_attribute('action') or "",
                    "method": await form.get_attribute('method') or "get",
                    "fields": []
                }
                forms.append(form_data)

            input_elements = await page.get_elements_by_css_selector('input, select, textarea')
            for inp in input_elements:
                try:
                    inp_type = await inp.get_attribute('type') or 'text'
                    inp_name = await inp.get_attribute('name') or ""
                    inp_placeholder = await inp.get_attribute('placeholder') or ""

                    inputs.append({
                        "type": inp_type,
                        "name": inp_name,
                        "placeholder": inp_placeholder,
                    })
                except Exception:
                    continue

            clickables = await page.get_elements_by_css_selector('button, a[href], [role="button"]')
            for elem in clickables[:50]:  # Limit to avoid processing too many
                try:
                    text = await elem.evaluate("(...args) => this.innerText || this.textContent || ''")
                    href = await elem.get_attribute('href')
                    tag = await elem.evaluate("(...args) => this.tagName.toLowerCase()")

                    if text and len(text.strip()) < 100:  # Skip very long text
                        actions.append({
                            "text": text.strip()[:50],
                            "href": href,
                            "tag": tag,
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"[Scout] Error extracting content: {e}")

        return {
            "forms": forms,
            "actions": actions,
            "inputs": inputs,
        }

    async def _find_clickable_elements(self, page) -> list:
        """Find all clickable elements that might lead to new pages."""
        clickables = []

        try:
            # Links using browser-use CDP API
            links = await page.get_elements_by_css_selector('a[href]')
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    text = await link.evaluate("(...args) => this.innerText || this.textContent || ''")

                    # Skip external links, anchors, javascript
                    if href and not href.startswith('#') and not href.startswith('javascript:'):
                        parsed = urlparse(href)
                        base_parsed = urlparse(self.base_url)

                        # Only internal links
                        if not parsed.netloc or parsed.netloc == base_parsed.netloc:
                            clickables.append({
                                "type": "link",
                                "href": href,
                                "text": text.strip()[:50] if text else "",
                                "selector": f'a[href="{href}"]',
                            })
                except Exception:
                    continue

            # Buttons that might trigger navigation using browser-use CDP API
            buttons = await page.get_elements_by_css_selector('button, [role="button"]')
            for btn in buttons[:20]:  # Limit buttons
                try:
                    text = await btn.evaluate("(...args) => this.innerText || this.textContent || ''")
                    if text and len(text.strip()) < 30:
                        btn_id = await btn.get_attribute('id')
                        if btn_id:
                            selector = f'#{btn_id}'
                        else:
                            selector = f'button'  # Simplified selector

                        clickables.append({
                            "type": "button",
                            "text": text.strip()[:30],
                            "selector": selector,
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"[Scout] Error finding clickables: {e}")

        return clickables[:30]  # Limit total clickables per page

    async def _save_page(self, page_data: dict) -> str:
        """Save a discovered page to the database."""
        async with AsyncSessionLocal() as db:
            page = DiscoveredPage(
                project_id=self.project_id,
                url=page_data["url"],
                path=page_data["path"],
                title=page_data.get("title"),
                page_type=page_data.get("page_type"),
                section=page_data.get("section"),
                state_hash=page_data.get("state_hash"),
                screenshot_url=page_data.get("screenshot_url"),
                forms_found=page_data.get("forms"),
                actions_found=page_data.get("actions"),
                inputs_found=page_data.get("inputs"),
                tables_found=page_data.get("tables"),
                llm_analysis=page_data.get("llm_analysis"),
                test_scenarios=page_data.get("test_scenarios"),
                requires_auth=page_data.get("requires_auth", False),
                required_permissions=page_data.get("required_permissions"),
                nav_steps=page_data.get("nav_steps"),
                depth=page_data.get("depth", 0),
                is_pattern_instance=page_data.get("is_pattern_instance", False),
                pattern_id=page_data.get("pattern_id"),
                is_feature=page_data.get("is_feature", False),
                feature_name=page_data.get("feature_name"),
                feature_description=page_data.get("feature_description"),
            )
            db.add(page)
            await db.commit()
            await db.refresh(page)
            return str(page.id)

    async def _save_connection(self, source_id: str, target_id: str, action: dict):
        """Save a connection between pages."""
        async with AsyncSessionLocal() as db:
            conn = PageConnection(
                project_id=self.project_id,
                source_page_id=source_id,
                target_page_id=target_id,
                action_type=action.get("type", "click"),
                action_selector=action.get("selector"),
                action_text=action.get("text"),
                step=action,
            )
            db.add(conn)
            await db.commit()

    async def _login_if_needed(self, page):
        """Attempt to login if credentials are provided."""
        if not self.credentials:
            return True

        await self._emit_activity("Attempting login...")

        try:
            username = self.credentials.get("username") or self.credentials.get("email")
            password = self.credentials.get("password")

            if not username or not password:
                await self._emit_activity("Missing credentials", "warning")
                return True  # Continue anyway

            # Try common login selectors
            username_selectors = [
                'input[name="email"]',
                'input[name="username"]',
                'input[type="email"]',
            ]

            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
            ]

            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
            ]

            # Find and fill username using browser-use CDP API
            for selector in username_selectors:
                try:
                    elements = await page.get_elements_by_css_selector(selector)
                    if elements and len(elements) > 0:
                        await elements[0].fill(username)
                        await self._emit_activity("Filled username field")
                        break
                except Exception:
                    continue

            # Find and fill password using browser-use CDP API
            for selector in password_selectors:
                try:
                    elements = await page.get_elements_by_css_selector(selector)
                    if elements and len(elements) > 0:
                        await elements[0].fill(password)
                        await self._emit_activity("Filled password field")
                        break
                except Exception:
                    continue

            # Submit using browser-use CDP API
            for selector in submit_selectors:
                try:
                    elements = await page.get_elements_by_css_selector(selector)
                    if elements and len(elements) > 0:
                        await elements[0].click()
                        await self._emit_activity("Clicked login button")
                        await asyncio.sleep(2)  # Wait for navigation
                        break
                except Exception:
                    continue

            await self._emit_activity("Login attempt completed", "success")
            return True

        except Exception as e:
            await self._emit_activity(f"Login failed: {e}", "error")
            return False

    async def _explore_page(self, url: str, depth: int, nav_steps: list, parent_page_id: str = None):
        """Explore a single page and discover its content."""
        if self.should_stop or self.stats["pages_discovered"] >= self.max_pages:
            return

        while self.paused:
            await asyncio.sleep(0.5)
            if self.should_stop:
                return

        try:
            page = await self.browser_session.get_current_page()
            if not page:
                return

            # Navigate to URL
            current_url = await page.get_url() if hasattr(page, 'get_url') else url
            if current_url != url:
                await self._emit_activity(f"Navigating to {url}")
                await page.goto(url)
                await asyncio.sleep(1)

            # Take screenshot
            screenshot = await self._take_screenshot()
            if screenshot and self.on_screenshot:
                await self.on_screenshot({
                    "image": screenshot,
                    "url": url,
                })

            title = await page.get_title() if hasattr(page, 'get_title') else None

            content = await self._extract_page_content(page)

            # Compute state hash for deduplication
            dom_markers = [a.get("text", "") for a in content["actions"][:10]]
            state_hash = self._compute_state_hash(url, dom_markers)

            if state_hash in self.visited_states:
                await self._emit_activity(f"Skipping duplicate state: {url}", "info")
                return

            self.visited_states.add(state_hash)

            # Try LLM analysis first, fall back to rule-based
            llm_analysis = await self._analyze_page_with_llm(page, url)

            if llm_analysis:
                await self._emit_activity(f"LLM analyzed: {llm_analysis.page_type} - {llm_analysis.page_description[:50]}...", "info")
                page_type = llm_analysis.page_type
                llm_features = llm_analysis.features
                page_description = llm_analysis.page_description
            else:
                # Fall back to rule-based classification
                page_type = self._classify_page_type(
                    content["forms"],
                    content["actions"],
                    url
                )
                llm_features = []
                page_description = None

            # Detect pattern
            pattern_id = self._detect_pattern(url, page_type)
            is_pattern_instance = False

            if pattern_id:
                if pattern_id in self.patterns:
                    # This is another instance of an existing pattern
                    self.patterns[pattern_id]["count"] += 1
                    is_pattern_instance = True
                    await self._emit_activity(f"Found another {pattern_id} page", "info")
                else:
                    # New pattern discovered
                    self.patterns[pattern_id] = {"count": 1, "representative_id": None}
                    self.stats["patterns_detected"] += 1
                    await self._emit_stats()

                    if self.on_pattern_detected:
                        await self.on_pattern_detected({
                            "pattern_id": pattern_id,
                            "example_url": url,
                        })

            section = self._extract_section(url, nav_steps)
            if section and section not in self.sections:
                self.sections.add(section)
                if self.on_section_found:
                    await self.on_section_found({
                        "name": section,
                        "url": url,
                    })

            # Determine if this is a feature (more selective - not every page is a feature)
            # Only mark as feature if it's an actionable page type, not just because LLM detected capabilities
            feature_page_types = ['login', 'register', 'form', 'form_create', 'form_edit', 'auth_form', 'settings', 'checkout']
            has_meaningful_forms = len(content["forms"]) > 0 and any(
                len(f.get("fields", [])) > 0 for f in content["forms"]
            )
            is_feature = (
                page_type in feature_page_types or  # Specific actionable page types
                has_meaningful_forms or  # Has forms with actual fields
                (pattern_id and not is_pattern_instance)  # First of a pattern
            )

            feature_name = None
            feature_description = None
            if is_feature:
                # Use LLM features if available, otherwise generate from rules
                if llm_features and len(llm_features) > 0:
                    feature_name = llm_features[0]
                    feature_description = page_description
                    for feat in llm_features:
                        self.stats["features_found"] += 1
                        if self.on_feature_found:
                            await self.on_feature_found({
                                "name": feat,
                                "url": url,
                                "page_type": page_type,
                                "description": page_description,
                            })
                else:
                    # Fall back to rule-based feature naming
                    if page_type == 'login':
                        feature_name = "User Login"
                    elif page_type == 'register':
                        feature_name = "User Registration"
                    elif page_type == 'form_create':
                        feature_name = f"Create {section.title() if section else 'Item'}"
                    elif page_type == 'form_edit':
                        feature_name = f"Edit {section.title() if section else 'Item'}"
                    elif page_type == 'settings':
                        feature_name = "Settings"
                    elif pattern_id:
                        feature_name = pattern_id.replace('_', ' ').title()
                    else:
                        feature_name = title or f"{page_type.title()} Page"

                    self.stats["features_found"] += 1
                    if self.on_feature_found:
                        await self.on_feature_found({
                            "name": feature_name,
                            "url": url,
                            "page_type": page_type,
                        })

                await self._emit_stats()

            parsed = urlparse(url)

            # Serialize LLM analysis if available
            llm_analysis_dict = None
            test_scenarios = None
            tables = None
            requires_auth = False
            required_permissions = None

            if llm_analysis:
                try:
                    llm_analysis_dict = llm_analysis.model_dump()
                    test_scenarios = llm_analysis.suggested_test_scenarios
                    tables = [t.model_dump() for t in llm_analysis.tables] if llm_analysis.tables else None
                    requires_auth = llm_analysis.requires_auth
                    required_permissions = llm_analysis.required_permissions
                except Exception as e:
                    print(f"[Scout] Error serializing LLM analysis: {e}")

            page_data = {
                "url": url,
                "path": parsed.path,
                "title": title,
                "page_type": page_type,
                "section": section,
                "state_hash": state_hash,
                "forms": content["forms"],
                "actions": content["actions"],
                "inputs": content["inputs"],
                "tables": tables,
                "llm_analysis": llm_analysis_dict,
                "test_scenarios": test_scenarios,
                "requires_auth": requires_auth,
                "required_permissions": required_permissions,
                "nav_steps": nav_steps,
                "depth": depth,
                "is_pattern_instance": is_pattern_instance,
                "pattern_id": pattern_id,
                "is_feature": is_feature,
                "feature_name": feature_name,
                "feature_description": feature_description,
            }

            page_id = await self._save_page(page_data)
            self.discovered_pages[url] = page_id

            if pattern_id and not is_pattern_instance:
                self.patterns[pattern_id]["representative_id"] = page_id

            if parent_page_id and nav_steps:
                last_step = nav_steps[-1] if nav_steps else {}
                await self._save_connection(parent_page_id, page_id, last_step)

                if self.on_connection_found:
                    await self.on_connection_found({
                        "source_id": parent_page_id,
                        "target_id": page_id,
                        "action": last_step,
                    })

            self.stats["pages_discovered"] += 1
            self.stats["current_depth"] = depth
            await self._emit_stats()

            if self.on_page_discovered:
                await self.on_page_discovered({
                    "id": page_id,
                    **page_data,
                })

            await self._emit_activity(f"Discovered: {title or url}", "success")

            # Don't explore deeper if this is a pattern instance
            if is_pattern_instance:
                return

            # Don't explore deeper if at max depth
            if depth >= self.max_depth:
                return

            # Find clickable elements for further exploration
            clickables = await self._find_clickable_elements(page)

            for clickable in clickables:
                href = clickable.get("href")
                if href:
                    # Resolve relative URLs
                    full_url = urljoin(url, href)
                    parsed_full = urlparse(full_url)
                    base_parsed = urlparse(self.base_url)

                    if parsed_full.netloc == base_parsed.netloc:
                        new_nav_steps = nav_steps + [{
                            "type": "click",
                            "selector": clickable.get("selector"),
                            "text": clickable.get("text"),
                            "url": full_url,
                        }]

                        self.queue.append((full_url, depth + 1, new_nav_steps, page_id))

        except Exception as e:
            await self._emit_activity(f"Error exploring {url}: {e}", "error")
            print(f"[Scout] Error exploring {url}: {e}")

    async def discover(self) -> dict:
        """
        Main discovery loop using BFS exploration.
        Returns discovery results.
        """
        self.running = True
        self.should_stop = False

        try:
            from browser_use.browser import BrowserSession

            await self._emit_activity("Starting discovery...")

            self.browser_session = BrowserSession(
                headless=settings.browser_use_headless,
                keep_alive=True,
            )
            await self.browser_session.start()
            await self._emit_activity(f"Browser initialized (headless={settings.browser_use_headless}, llm={settings.browser_use_llm_provider})")

            page = await self.browser_session.get_current_page()
            if not page:
                raise Exception("Failed to get browser page")

            start_url = self.base_url
            if self.credentials:
                # Navigate to login page first
                login_url = urljoin(self.base_url, '/login')
                await self._emit_activity(f"Navigating to login page: {login_url}")
                await page.goto(login_url)
                await asyncio.sleep(2)

                # Perform login
                login_success = await self._login_if_needed(page)
                await asyncio.sleep(3)

                if login_success:
                    try:
                        start_url = await page.get_url()
                        await self._emit_activity(f"Logged in, starting from: {start_url}")
                    except Exception:
                        start_url = self.base_url
            else:
                # No credentials, just go to base URL
                await self._emit_activity(f"Navigating to {self.base_url}")
                await page.goto(self.base_url)
                await asyncio.sleep(2)

            # Take initial screenshot
            screenshot = await self._take_screenshot()
            if screenshot and self.on_screenshot:
                await self.on_screenshot({
                    "image": screenshot,
                    "url": start_url,
                })

            self.queue.append((start_url, 0, [], None))

            while self.queue and not self.should_stop:
                if self.stats["pages_discovered"] >= self.max_pages:
                    await self._emit_activity(f"Reached max pages limit ({self.max_pages})")
                    break

                url, depth, nav_steps, parent_id = self.queue.popleft()

                # Skip if already visited
                if url in self.discovered_pages:
                    continue

                await self._explore_page(url, depth, nav_steps, parent_id)

                # Small delay between pages
                await asyncio.sleep(0.5)

            await self._emit_activity("Discovery completed!", "success")

            return {
                "success": True,
                "pages_discovered": self.stats["pages_discovered"],
                "features_found": self.stats["features_found"],
                "patterns_detected": self.stats["patterns_detected"],
                "sections": list(self.sections),
            }

        except Exception as e:
            await self._emit_activity(f"Discovery failed: {e}", "error")
            return {
                "success": False,
                "message": str(e),
                "pages_discovered": self.stats["pages_discovered"],
                "features_found": self.stats["features_found"],
                "patterns_detected": self.stats["patterns_detected"],
            }

        finally:
            self.running = False
            if self.browser_session:
                try:
                    await self.browser_session.close()
                except Exception:
                    pass
