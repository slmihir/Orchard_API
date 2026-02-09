"""
Variant Generator - Creates test variants from recorded steps.

This analyzes recorded test steps and generates variants by:
1. Detecting "setup" vs "test" portions (login is setup, unique actions are test)
2. Finding "fill" actions in the TEST portion only
3. Generating variant values (negative, boundary, security, etc.)
4. Deduplicating - won't regenerate variants for identical step patterns
"""

import re
import copy
import hashlib
import json
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import get_settings

settings = get_settings()

# In-memory cache of patterns that already have variants
# Key: pattern_hash, Value: list of variant types generated
_generated_patterns: dict[str, list[str]] = {}


class VariantGenerator:
    """
    Generates test variants from recorded steps using LLM analysis.

    Smart features:
    - Detects setup (login/nav) vs test (unique actions) portions
    - Only generates variants for the test portion
    - Deduplicates - won't regenerate for identical patterns
    """

    def __init__(self):
        # Use Gemini 3.0 Flash for variant generation
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=settings.google_api_key,
            model_kwargs={"response_mime_type": "application/json"},
        )

    async def generate_variants(
        self,
        steps: list[dict],
        variant_types: list[str] = None,
        test_name: str = "",
        test_description: str = "",
        project_id: str = None,
        skip_setup_variants: bool = True,
    ) -> dict:
        """
        Generate test variants from recorded steps.

        Args:
            steps: List of recorded step dicts [{type, selector, value, ...}]
            variant_types: Types of variants to generate (None = auto-select)
            test_name: Name of the original test
            test_description: Description of what the test does
            project_id: Project ID for deduplication tracking
            skip_setup_variants: If True, don't generate variants for setup steps

        Returns:
            Dict containing:
            - variants: List of variant dicts
            - setup_boundary: Index where setup ends and test begins
            - setup_variants_skipped: Whether setup variants were skipped
            - pattern_hash: Hash of the test portion for deduplication
        """
        if not steps:
            return {"variants": [], "setup_boundary": 0, "setup_variants_skipped": False}

        # Step 1: Detect setup vs test boundary
        analysis = await self._analyze_step_boundaries(steps, test_name, test_description)
        setup_boundary = analysis.get("setup_boundary", 0)
        setup_type = analysis.get("setup_type", "none")

        print(f"[VariantGenerator] Setup boundary at step {setup_boundary}, type: {setup_type}")

        test_steps = steps[setup_boundary:] if skip_setup_variants else steps
        test_step_offset = setup_boundary if skip_setup_variants else 0

        # Step 3: Check for duplicate patterns (disabled for now - not persisting variants yet)
        pattern_hash = self._hash_steps(test_steps)
        # cache_key = f"{project_id or 'global'}:{pattern_hash}"
        #
        # if cache_key in _generated_patterns:
        #     print(f"[VariantGenerator] Pattern already has variants, skipping: {cache_key[:20]}...")
        #     return {
        #         "variants": [],
        #         "setup_boundary": setup_boundary,
        #         "setup_variants_skipped": skip_setup_variants and setup_boundary > 0,
        #         "pattern_hash": pattern_hash,
        #         "duplicate_skipped": True,
        #     }

        # Step 4: Find fill actions in test portion only
        fill_actions = self._extract_fill_actions(test_steps, offset=test_step_offset)

        if not fill_actions:
            return {
                "variants": [],
                "setup_boundary": setup_boundary,
                "setup_variants_skipped": skip_setup_variants and setup_boundary > 0,
                "pattern_hash": pattern_hash,
            }

        # Step 5: Generate variants for test portion
        variants = await self._generate_variants_with_llm(
            steps=steps,  # Full steps for context
            fill_actions=fill_actions,  # Only test portion fills
            variant_types=variant_types,
            test_name=test_name,
            test_description=test_description,
            setup_boundary=setup_boundary,
        )

        # Mark pattern as processed (disabled - not persisting yet)
        # _generated_patterns[cache_key] = [v["type"] for v in variants]

        return {
            "variants": variants,
            "setup_boundary": setup_boundary,
            "setup_type": setup_type,
            "setup_variants_skipped": skip_setup_variants and setup_boundary > 0,
            "pattern_hash": pattern_hash,
        }

    async def _analyze_step_boundaries(
        self, steps: list[dict], test_name: str, test_description: str
    ) -> dict:
        """Use LLM to detect where setup ends and the actual test begins."""
        step_summary = []
        for i, step in enumerate(steps):
            step_type = step.get("type", "unknown")
            selector = (step.get("selector") or "")[:50]
            value = (step.get("value") or "")[:30]

            hints = []
            selector_lower = selector.lower()
            if any(x in selector_lower for x in ["login", "signin", "auth"]):
                hints.append("login-related")
            if any(x in selector_lower for x in ["email", "username", "user"]):
                hints.append("credential-field")
            if any(x in selector_lower for x in ["password", "pwd"]):
                hints.append("password-field")
            if any(x in selector_lower for x in ["submit", "login", "signin"]):
                hints.append("submit-button")

            hint_str = f" [{', '.join(hints)}]" if hints else ""
            step_summary.append(f"{i}: {step_type} | {selector}{hint_str} | value: {value}")

        prompt = f"""Analyze this test flow and identify where the "setup" portion ends and the actual "test" begins.

Test Name: {test_name or "Unknown"}
Test Description: {test_description or "A recorded user interaction test"}

Steps:
{chr(10).join(step_summary)}

Setup typically includes:
- Login/authentication flows
- Navigation to a specific page/section
- Any prerequisite actions before the main test

The actual test is:
- The unique actions being tested
- Form submissions being validated
- Features being exercised

Respond in JSON:
{{
    "setup_boundary": <step_index where setup ends and test begins, 0 if no setup>,
    "setup_type": "login|navigation|prerequisite|none",
    "setup_description": "Brief description of what the setup does",
    "test_description": "Brief description of what the actual test does"
}}

If the entire flow is a login test (testing login itself), set setup_boundary to 0."""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content

            print(f"[VariantGenerator] Boundary LLM response type: {type(content)}")
            print(f"[VariantGenerator] Boundary LLM response: {str(content)[:300]}")

            if isinstance(content, list) and content:
                if isinstance(content[0], dict) and 'text' in content[0]:
                    content = content[0]['text']
                else:
                    content = str(content[0])

            content_str = str(content)

            # Try to extract JSON from markdown code blocks first
            code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content_str)
            if code_block_match:
                content_str = code_block_match.group(1)

            json_match = re.search(r'\{[\s\S]*\}', content_str)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"[VariantGenerator] Boundary detection error: {e}")

        # Fallback: simple heuristic detection
        return self._detect_setup_heuristic(steps)

    def _detect_setup_heuristic(self, steps: list[dict]) -> dict:
        """Fallback heuristic to detect login/setup steps."""
        setup_boundary = 0

        for i, step in enumerate(steps):
            selector = (step.get("selector") or "").lower()
            value = (step.get("value") or "").lower()
            step_type = (step.get("type") or "").lower()

            # Look for login indicators
            is_login_related = any(x in selector for x in [
                "login", "signin", "sign-in", "auth",
                "email", "username", "password"
            ])

            # Look for submit after credentials
            is_submit = step_type == "click" and any(x in selector for x in [
                "submit", "login", "signin", "button"
            ])

            if is_login_related or (is_submit and i > 0):
                setup_boundary = i + 1  # Setup ends after this step
            else:
                # First non-login step after login steps = test starts
                if setup_boundary > 0:
                    break

        return {
            "setup_boundary": setup_boundary,
            "setup_type": "login" if setup_boundary > 0 else "none",
        }

    def _hash_steps(self, steps: list[dict]) -> str:
        """Create a hash of step patterns for deduplication."""
        # Hash based on step types and selectors (not values)
        pattern_parts = []
        for step in steps:
            step_type = step.get("type") or ""
            selector = step.get("selector") or ""
            pattern_parts.append(f"{step_type}:{selector}")

        pattern_str = "|".join(pattern_parts)
        return hashlib.md5(pattern_str.encode()).hexdigest()[:16]

    def _extract_fill_actions(self, steps: list[dict], offset: int = 0) -> list[dict]:
        """Extract fill/input actions from steps that can have variants."""
        fill_actions = []

        for i, step in enumerate(steps):
            step_type = (step.get("type") or "").lower()

            if step_type in ["fill", "input", "type"]:
                fill_actions.append({
                    "index": i + offset,  # Actual index in full step list
                    "local_index": i,
                    "selector": step.get("selector") or "",
                    "value": step.get("value") or "",
                    "selector_info": step.get("selector_info") or {},
                })

        return fill_actions

    async def _generate_variants_with_llm(
        self,
        steps: list[dict],
        fill_actions: list[dict],
        variant_types: list[str],
        test_name: str,
        test_description: str,
        setup_boundary: int,
    ) -> list[dict]:
        """Use LLM to intelligently generate variants."""
        fill_context = []
        for action in fill_actions:
            selector = action["selector"]
            value = action["value"]
            info = action["selector_info"]

            attrs = info.get("attributes", {}) if isinstance(info, dict) else {}

            fill_context.append({
                "step_index": action["index"],
                "selector": selector,
                "original_value": value,
                "field_name": attrs.get("name", ""),
                "field_type": attrs.get("type", ""),
                "placeholder": attrs.get("placeholder", ""),
                "aria_label": attrs.get("aria-label", ""),
            })

        setup_note = ""
        if setup_boundary > 0:
            setup_note = f"\nNOTE: Steps 0-{setup_boundary-1} are SETUP (login/navigation). Generate variants ONLY for steps {setup_boundary}+ which are the actual test.\n"

        step_list = []
        for i, step in enumerate(steps):
            step_type = step.get("type", "unknown")
            selector = (step.get("selector") or "")[:40]
            value = (step.get("value") or "")[:20]
            step_list.append(f"{i}: {step_type} | {selector} | {value}")

        prompt = f"""Generate test variants for this recorded test.

ALL STEPS:
{chr(10).join(step_list)}

FILL FIELDS TO VARY:
{self._format_fill_context(fill_context)}

Return JSON:
{{"variants": [
  {{
    "name": "variant name",
    "type": "negative|empty|security|boundary",
    "changes": [{{"step_index": N, "new_value": "value"}}],
    "expected_result": "describe the expected error (e.g., 'email validation error', 'password required')",
    "assertion": {{"type": "assert_text", "selector": "body", "expected": "placeholder", "operator": "contains", "insert_after_step": N}},
    "truncate_after_step": N
  }}
]}}

RULES:
1. insert_after_step = the CLICK step right after the field you modified
2. truncate_after_step = same as insert_after_step
3. For email field changes: use the click IMMEDIATELY after the email fill
4. For password field changes: use the click IMMEDIATELY after the password fill
5. assertion.expected can be "placeholder" - we will discover the real error by running the test

Generate 3-4 variants."""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content

            print(f"[VariantGenerator] Raw LLM response type: {type(content)}")
            print(f"[VariantGenerator] Raw LLM response: {str(content)[:500]}")

            if isinstance(content, list) and content:
                if isinstance(content[0], dict) and 'text' in content[0]:
                    content = content[0]['text']
                else:
                    content = str(content[0])

            content_str = str(content)

            # Try to extract JSON from markdown code blocks first
            code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content_str)
            if code_block_match:
                content_str = code_block_match.group(1)

            json_match = re.search(r'\{[\s\S]*\}', content_str)
            if not json_match:
                print(f"[VariantGenerator] No JSON found in response")
                return []

            result = json.loads(json_match.group())
            raw_variants = result.get("variants", [])

            final_variants = []
            for variant in raw_variants:
                print(f"[VariantGenerator] Processing variant: {variant.get('name')}")
                print(f"[VariantGenerator] truncate_after_step: {variant.get('truncate_after_step')}")
                print(f"[VariantGenerator] assertion: {variant.get('assertion')}")

                modified_steps = self._apply_changes(steps, variant.get("changes", []))
                print(f"[VariantGenerator] Steps before truncate: {len(modified_steps)}")

                # Truncate steps if specified (for validation that stops the flow)
                truncate_after = variant.get("truncate_after_step")
                if truncate_after is not None and isinstance(truncate_after, int):
                    modified_steps = modified_steps[:truncate_after + 1]
                    print(f"[VariantGenerator] Steps after truncate at {truncate_after}: {len(modified_steps)}")

                assertion = variant.get("assertion")
                if assertion:
                    assertion_step = self._build_assertion_step(assertion)
                    if assertion_step:
                        insert_after = assertion.get("insert_after_step")
                        print(f"[VariantGenerator] insert_after_step: {insert_after}")
                        if insert_after is not None and isinstance(insert_after, int):
                            insert_pos = min(insert_after + 1, len(modified_steps))
                            print(f"[VariantGenerator] Inserting assertion at position {insert_pos}")
                            modified_steps.insert(insert_pos, assertion_step)
                        else:
                            # Default: append at end
                            print(f"[VariantGenerator] No insert_after_step, appending at end")
                            modified_steps.append(assertion_step)

                final_variants.append({
                    "name": variant.get("name", "Unnamed Variant"),
                    "type": variant.get("type", "negative"),
                    "description": variant.get("description", ""),
                    "steps": modified_steps,
                    "expected_result": variant.get("expected_result", ""),
                    "has_assertion": assertion is not None,
                })

            return final_variants

        except Exception as e:
            print(f"[VariantGenerator] LLM error: {e}")
            return []

    def _format_fill_context(self, fill_context: list[dict]) -> str:
        """Format fill context for the LLM prompt."""
        lines = []
        for i, ctx in enumerate(fill_context):
            lines.append(f"Field {i + 1}:")
            lines.append(f"  - Step index: {ctx['step_index']}")
            lines.append(f"  - Selector: {ctx['selector']}")
            lines.append(f"  - Current value: {ctx['original_value']}")
            if ctx['field_name']:
                lines.append(f"  - Field name: {ctx['field_name']}")
            if ctx['field_type']:
                lines.append(f"  - Input type: {ctx['field_type']}")
            if ctx['placeholder']:
                lines.append(f"  - Placeholder: {ctx['placeholder']}")
            if ctx['aria_label']:
                lines.append(f"  - Aria label: {ctx['aria_label']}")
            lines.append("")
        return "\n".join(lines)

    def _apply_changes(self, original_steps: list[dict], changes: list[dict]) -> list[dict]:
        """Apply variant changes to create modified steps."""
        modified_steps = copy.deepcopy(original_steps)

        for change in changes:
            step_index = change.get("step_index")
            new_value = change.get("new_value")

            if step_index is not None and 0 <= step_index < len(modified_steps):
                modified_steps[step_index]["value"] = new_value
                # Mark as modified for tracking
                modified_steps[step_index]["_variant_modified"] = True
                modified_steps[step_index]["_original_value"] = original_steps[step_index].get("value")

        return modified_steps

    def _build_assertion_step(self, assertion: dict) -> Optional[dict]:
        """Build a Playwright assertion step from LLM-generated assertion config."""
        if not assertion:
            return None

        assertion_type = assertion.get("type", "assert_text")
        expected = assertion.get("expected", "placeholder")

        step = {
            "type": assertion_type,
            "selector": assertion.get("selector", ""),
            "value": "",
            "_variant_assertion": True,
        }

        if assertion_type == "assert_vision":
            step["assertion_config"] = {
                "expected": expected,
            }
        elif assertion_type in ["assert_text", "assert_value"]:
            step["assertion_config"] = {
                "expected": expected,
                "operator": assertion.get("operator", "contains"),
            }
        elif assertion_type == "assert_visible":
            step["assertion_config"] = {
                "expected": "",
                "operator": "equals",
            }
        elif assertion_type == "assert_hidden":
            step["assertion_config"] = {
                "expected": "",
                "operator": "equals",
            }

        return step


def clear_pattern_cache(project_id: str = None):
    """Clear the pattern cache, optionally for a specific project."""
    global _generated_patterns
    if project_id:
        keys_to_remove = [k for k in _generated_patterns if k.startswith(f"{project_id}:")]
        for k in keys_to_remove:
            del _generated_patterns[k]
    else:
        _generated_patterns = {}
