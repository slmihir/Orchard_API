from app.models.test import Step


def generate_playwright_code(steps: list[Step], test_name: str = "generated_test") -> str:
    """Convert steps to executable Playwright Python code."""

    lines = [
        "from playwright.sync_api import sync_playwright",
        "import time",
        "",
        f"def {test_name}():",
        "    with sync_playwright() as p:",
        "        browser = p.chromium.launch(headless=True)",
        "        page = browser.new_page()",
        "        ",
        "        try:",
    ]

    for step in steps:
        indent = "            "  # 12 spaces
        step_code = generate_step_code(step)
        if step_code:
            lines.append(f"{indent}{step_code}")

    lines.extend([
        "            ",
        "            print('Test passed!')",
        "        except Exception as e:",
        "            print(f'Test failed: {e}')",
        "            raise",
        "        finally:",
        "            browser.close()",
        "",
        f"if __name__ == '__main__':",
        f"    {test_name}()",
    ])

    return "\n".join(lines)


def generate_step_code(step: Step) -> str | None:
    """Generate code for a single step."""
    step_type = step.type
    selector = escape_string(step.selector) if step.selector else None
    value = escape_string(step.value) if step.value else None

    if step_type == "navigate":
        return f'page.goto("{value}")'

    elif step_type == "click":
        return f'page.click("{selector}")'

    elif step_type == "fill":
        return f'page.fill("{selector}", "{value or ""}")'

    elif step_type == "wait":
        wait_ms = int(value) if value else 1000
        return f'time.sleep({wait_ms / 1000})'

    elif step_type == "scroll":
        if selector:
            return f'page.locator("{selector}").scroll_into_view_if_needed()'
        return 'page.evaluate("window.scrollBy(0, 500)")'

    elif step_type == "hover":
        return f'page.hover("{selector}")'

    elif step_type == "assert":
        if selector:
            return f'page.wait_for_selector("{selector}", timeout=5000)'
        if value:
            return f'assert "{value}" in page.content(), "Text not found: {value}"'

    return None


def escape_string(s: str) -> str:
    """Escape string for Python code."""
    if not s:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def generate_playwright_typescript(steps: list[Step], test_name: str = "generatedTest") -> str:
    """Generate Playwright TypeScript code (for future use)."""

    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"test('{test_name}', async ({{ page }}) => {{",
    ]

    for step in steps:
        step_code = generate_step_code_ts(step)
        if step_code:
            lines.append(f"  {step_code}")

    lines.append("});")

    return "\n".join(lines)


def generate_step_code_ts(step: Step) -> str | None:
    """Generate TypeScript code for a single step."""
    step_type = step.type
    selector = escape_string(step.selector) if step.selector else None
    value = escape_string(step.value) if step.value else None

    if step_type == "navigate":
        return f"await page.goto('{value}');"

    elif step_type == "click":
        return f"await page.click('{selector}');"

    elif step_type == "fill":
        return f"await page.fill('{selector}', '{value or ''}');"

    elif step_type == "wait":
        wait_ms = int(value) if value else 1000
        return f"await page.waitForTimeout({wait_ms});"

    elif step_type == "scroll":
        if selector:
            return f"await page.locator('{selector}').scrollIntoViewIfNeeded();"
        return "await page.evaluate(() => window.scrollBy(0, 500));"

    elif step_type == "hover":
        return f"await page.hover('{selector}');"

    elif step_type == "assert":
        if selector:
            return f"await expect(page.locator('{selector}')).toBeVisible();"
        if value:
            return f"await expect(page.content()).toContain('{value}');"

    return None
