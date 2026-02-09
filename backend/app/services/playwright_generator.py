"""Generate Playwright test code from captured steps."""

from typing import List
from datetime import datetime


def generate_playwright_test(
    test_name: str,
    steps: List[dict],
    target_url: str = None
) -> str:
    """Generate a complete Playwright test from captured steps."""

    # Clean test name for function
    safe_name = test_name.lower().replace(' ', '_').replace('-', '_')
    safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '_')

    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"test('{test_name}', async ({{ page }}) => {{",
    ]

    for i, step in enumerate(steps):
        # Skip wait steps if followed by an assertion (assertion already waits)
        if step.get('type') == 'wait':
            next_step = steps[i + 1] if i + 1 < len(steps) else None
            if next_step and next_step.get('type', '').startswith('assert_'):
                continue  # Skip this wait

        step_code = _generate_step_code(step)
        if step_code:
            lines.append(f"  {step_code}")

    lines.append("});")
    lines.append("")

    return "\n".join(lines)


def generate_playwright_python(
    test_name: str,
    steps: List[dict],
    target_url: str = None
) -> str:
    """Generate Python Playwright test from captured steps."""

    safe_name = test_name.lower().replace(' ', '_').replace('-', '_')
    safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '_')

    lines = [
        "import pytest",
        "from playwright.sync_api import Page, expect",
        "",
        "",
        f"def test_{safe_name}(page: Page):",
        f'    """Test: {test_name}"""',
    ]

    for i, step in enumerate(steps):
        # Skip wait steps if followed by an assertion (assertion already waits)
        if step.get('type') == 'wait':
            next_step = steps[i + 1] if i + 1 < len(steps) else None
            if next_step and next_step.get('type', '').startswith('assert_'):
                continue  # Skip this wait

        step_code = _generate_step_code_python(step)
        if step_code:
            lines.append(f"    {step_code}")

    lines.append("")

    return "\n".join(lines)


def _escape_selector_ts(selector: str) -> str:
    """Escape a selector for use in TypeScript single-quoted strings."""
    # Replace single quotes with escaped single quotes
    return selector.replace("'", "\\'")


def _generate_step_code(step: dict) -> str:
    """Generate TypeScript Playwright code for a single step."""
    step_type = step.get('type', '')
    selector = step.get('selector', '')
    value = step.get('value', '')

    if step_type == 'navigate':
        escaped_value = value.replace("'", "\\'")
        return f"await page.goto('{escaped_value}');"

    elif step_type == 'click':
        if selector:
            escaped_selector = _escape_selector_ts(selector)
            return f"await page.locator('{escaped_selector}').click();"
        return f"// Click action - selector not captured"

    elif step_type == 'fill':
        if selector and value:
            escaped_selector = _escape_selector_ts(selector)
            escaped_value = value.replace("'", "\\'")
            return f"await page.locator('{escaped_selector}').fill('{escaped_value}');"
        return f"// Fill action - selector or value not captured"

    elif step_type == 'wait':
        seconds = value if value else 1
        try:
            ms = int(float(seconds) * 1000) if isinstance(seconds, (int, float, str)) else 1000
        except:
            ms = 1000
        return f"await page.waitForTimeout({ms});"

    elif step_type == 'scroll':
        if selector:
            escaped_selector = _escape_selector_ts(selector)
            return f"await page.locator('{escaped_selector}').scrollIntoViewIfNeeded();"
        return "await page.mouse.wheel(0, 300);"

    elif step_type == 'hover':
        if selector:
            escaped_selector = _escape_selector_ts(selector)
            return f"await page.locator('{escaped_selector}').hover();"
        return f"// Hover action - selector not captured"

    elif step_type == 'assert_visible':
        if selector:
            escaped_selector = _escape_selector_ts(selector)
            return f"await expect(page.locator('{escaped_selector}')).toBeVisible();"
        return f"// Assert visible - selector not captured"

    elif step_type == 'assert_hidden':
        if selector:
            escaped_selector = _escape_selector_ts(selector)
            return f"await expect(page.locator('{escaped_selector}')).toBeHidden();"
        return f"// Assert hidden - selector not captured"

    elif step_type == 'assert_text':
        config = step.get('assertion_config', {})
        expected = config.get('expected', '')
        operator = config.get('operator', 'equals')
        if selector:
            escaped_selector = _escape_selector_ts(selector)
            escaped_expected = expected.replace("'", "\\'")
            if operator == 'contains':
                return f"await expect(page.locator('{escaped_selector}')).toContainText('{escaped_expected}');"
            elif operator == 'matches':
                return f"await expect(page.locator('{escaped_selector}')).toHaveText(/{escaped_expected}/);"
            else:
                return f"await expect(page.locator('{escaped_selector}')).toHaveText('{escaped_expected}');"
        return f"// Assert text - selector not captured"

    elif step_type == 'assert_value':
        config = step.get('assertion_config', {})
        expected = config.get('expected', '')
        if selector:
            escaped_selector = _escape_selector_ts(selector)
            escaped_expected = expected.replace("'", "\\'")
            return f"await expect(page.locator('{escaped_selector}')).toHaveValue('{escaped_expected}');"
        return f"// Assert value - selector not captured"

    elif step_type == 'assert_attribute':
        config = step.get('assertion_config', {})
        expected = config.get('expected', '')
        attribute = config.get('attribute', '')
        if selector and attribute:
            escaped_selector = _escape_selector_ts(selector)
            escaped_expected = expected.replace("'", "\\'")
            return f"await expect(page.locator('{escaped_selector}')).toHaveAttribute('{attribute}', '{escaped_expected}');"
        return f"// Assert attribute - selector or attribute not captured"

    elif step_type == 'assert_url':
        config = step.get('assertion_config', {})
        expected = config.get('expected', '')
        operator = config.get('operator', 'equals')
        escaped_expected = expected.replace("'", "\\'")
        # Use waitForURL (waits for navigation with timeout)
        if operator == 'contains':
            return f"await page.waitForURL('**{escaped_expected}**', {{ timeout: 10000 }});"
        else:
            return f"await page.waitForURL('{escaped_expected}', {{ timeout: 10000 }});"

    elif step_type == 'assert_api':
        config = step.get('assertion_config', {})
        api_url_pattern = config.get('api_url_pattern', '')
        api_status = config.get('api_status', 200)
        return f"// API assertion: {api_url_pattern} should return {api_status}"

    elif step_type == 'done':
        return "// Automation completed"

    return f"// Unknown step type: {step_type}"


def _generate_step_code_python(step: dict) -> str:
    """Generate Python Playwright code for a single step."""
    step_type = step.get('type', '')
    selector = step.get('selector', '')
    value = step.get('value', '')

    if step_type == 'navigate':
        return f'page.goto("{value}")'

    elif step_type == 'click':
        if selector:
            return f'page.locator("{selector}").click()'
        return f"# Click action - selector not captured"

    elif step_type == 'fill':
        if selector and value:
            escaped_value = value.replace('"', '\\"')
            return f'page.locator("{selector}").fill("{escaped_value}")'
        return f"# Fill action - selector or value not captured"

    elif step_type == 'wait':
        seconds = value if value else 1
        try:
            ms = int(float(seconds) * 1000) if isinstance(seconds, (int, float, str)) else 1000
        except:
            ms = 1000
        return f"page.wait_for_timeout({ms})"

    elif step_type == 'scroll':
        if selector:
            return f'page.locator("{selector}").scroll_into_view_if_needed()'
        return "page.mouse.wheel(0, 300)"

    elif step_type == 'hover':
        if selector:
            return f'page.locator("{selector}").hover()'
        return f"# Hover action - selector not captured"

    elif step_type == 'assert_visible':
        if selector:
            return f'expect(page.locator("{selector}")).to_be_visible()'
        return f"# Assert visible - selector not captured"

    elif step_type == 'assert_hidden':
        if selector:
            return f'expect(page.locator("{selector}")).to_be_hidden()'
        return f"# Assert hidden - selector not captured"

    elif step_type == 'assert_text':
        config = step.get('assertion_config', {})
        expected = config.get('expected', '').replace('"', '\\"')
        operator = config.get('operator', 'equals')
        if selector:
            if operator == 'contains':
                return f'expect(page.locator("{selector}")).to_contain_text("{expected}")'
            else:
                return f'expect(page.locator("{selector}")).to_have_text("{expected}")'
        return f"# Assert text - selector not captured"

    elif step_type == 'assert_value':
        config = step.get('assertion_config', {})
        expected = config.get('expected', '').replace('"', '\\"')
        if selector:
            return f'expect(page.locator("{selector}")).to_have_value("{expected}")'
        return f"# Assert value - selector not captured"

    elif step_type == 'assert_attribute':
        config = step.get('assertion_config', {})
        expected = config.get('expected', '').replace('"', '\\"')
        attribute = config.get('attribute', '')
        if selector and attribute:
            return f'expect(page.locator("{selector}")).to_have_attribute("{attribute}", "{expected}")'
        return f"# Assert attribute - selector or attribute not captured"

    elif step_type == 'assert_url':
        config = step.get('assertion_config', {})
        expected = config.get('expected', '').replace('"', '\\"')
        operator = config.get('operator', 'equals')
        if operator == 'contains':
            return f'expect(page).to_have_url(re.compile(r"{expected}"))'
        else:
            return f'expect(page).to_have_url("{expected}")'

    elif step_type == 'assert_api':
        config = step.get('assertion_config', {})
        api_url_pattern = config.get('api_url_pattern', '')
        api_status = config.get('api_status', 200)
        return f"# API assertion: {api_url_pattern} should return {api_status}"

    elif step_type == 'done':
        return "# Automation completed"

    return f"# Unknown step type: {step_type}"
