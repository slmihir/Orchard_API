"""Variable resolution for API test templates."""

import re
import json
from typing import Any


class VariableResolver:
    """
    Resolves {{variable}} patterns in strings with values from context.

    Supports:
    - Simple variables: {{base_url}}
    - Nested paths: {{response.data.id}}
    - Array access: {{users.0.name}}
    """

    VARIABLE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')

    def resolve(self, template: str | None, context: dict) -> str:
        """
        Resolve variables in a string template.

        Args:
            template: String containing {{variable}} patterns
            context: Dictionary of variable values

        Returns:
            String with variables replaced by their values
        """
        if not template:
            return template or ""

        if not isinstance(template, str):
            return str(template)

        def replacer(match: re.Match) -> str:
            var_path = match.group(1).strip()
            value = self._get_value(var_path, context)
            if value is None:
                # Keep original placeholder if variable not found
                return match.group(0)
            # Convert to string
            if isinstance(value, (dict, list)):
                return json.dumps(value)
            return str(value)

        return self.VARIABLE_PATTERN.sub(replacer, template)

    def resolve_dict(self, obj: dict | None, context: dict) -> dict:
        """
        Recursively resolve variables in a dictionary.

        Args:
            obj: Dictionary containing string values with {{variable}} patterns
            context: Dictionary of variable values

        Returns:
            Dictionary with all string values resolved
        """
        if not obj:
            return obj or {}

        result = {}
        for key, value in obj.items():
            # Resolve the key too (in case it has variables)
            resolved_key = self.resolve(key, context) if isinstance(key, str) else key

            if isinstance(value, str):
                result[resolved_key] = self.resolve(value, context)
            elif isinstance(value, dict):
                result[resolved_key] = self.resolve_dict(value, context)
            elif isinstance(value, list):
                result[resolved_key] = self.resolve_list(value, context)
            else:
                result[resolved_key] = value

        return result

    def resolve_list(self, arr: list | None, context: dict) -> list:
        """
        Recursively resolve variables in a list.

        Args:
            arr: List containing items with {{variable}} patterns
            context: Dictionary of variable values

        Returns:
            List with all string values resolved
        """
        if not arr:
            return arr or []

        result = []
        for item in arr:
            if isinstance(item, str):
                result.append(self.resolve(item, context))
            elif isinstance(item, dict):
                result.append(self.resolve_dict(item, context))
            elif isinstance(item, list):
                result.append(self.resolve_list(item, context))
            else:
                result.append(item)

        return result

    def resolve_any(self, value: Any, context: dict) -> Any:
        """
        Resolve variables in any type of value.

        Args:
            value: Any value that might contain {{variable}} patterns
            context: Dictionary of variable values

        Returns:
            Value with all string patterns resolved
        """
        if isinstance(value, str):
            return self.resolve(value, context)
        elif isinstance(value, dict):
            return self.resolve_dict(value, context)
        elif isinstance(value, list):
            return self.resolve_list(value, context)
        else:
            return value

    def _get_value(self, path: str, context: dict) -> Any:
        """
        Get value from context using dot notation.

        Args:
            path: Path to value using dot notation (e.g., 'response.data.id')
            context: Dictionary of variable values

        Returns:
            Value at path or None if not found

        Examples:
            - "base_url" -> context["base_url"]
            - "response.data.id" -> context["response"]["data"]["id"]
            - "users.0.name" -> context["users"][0]["name"]
        """
        parts = path.split('.')
        current = context

        for part in parts:
            if current is None:
                return None

            # Try to access as dict key first
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return None

            # Try to access as list index
            elif isinstance(current, list):
                try:
                    index = int(part)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                except ValueError:
                    return None

            # Try to access as object attribute
            elif hasattr(current, part):
                current = getattr(current, part)

            else:
                return None

        return current

    def has_variables(self, template: str | None) -> bool:
        """Check if a string contains any {{variable}} patterns."""
        if not template or not isinstance(template, str):
            return False
        return bool(self.VARIABLE_PATTERN.search(template))

    def extract_variables(self, template: str | None) -> list[str]:
        """Extract all variable names from a template."""
        if not template or not isinstance(template, str):
            return []
        return [match.group(1).strip() for match in self.VARIABLE_PATTERN.finditer(template)]

    def build_context(
        self,
        environment_vars: dict | None = None,
        collection_vars: dict | None = None,
        runtime_vars: dict | None = None,
        extracted_vars: dict | None = None,
    ) -> dict:
        """
        Build execution context by merging variable sources.

        Priority (highest to lowest):
        1. extracted_vars - Variables extracted from previous responses
        2. runtime_vars - Variables passed at execution time
        3. collection_vars - Variables defined on the collection
        4. environment_vars - Variables from the selected environment

        Args:
            environment_vars: Variables from APIEnvironment
            collection_vars: Variables from APICollection
            runtime_vars: Variables passed during execution
            extracted_vars: Variables extracted during test run

        Returns:
            Merged context dictionary
        """
        context = {}

        # Apply in order of priority (lowest first, so higher priority overwrites)
        if environment_vars:
            for key, val in environment_vars.items():
                # Handle EnvironmentVariable structure
                if isinstance(val, dict) and "value" in val:
                    context[key] = val["value"]
                else:
                    context[key] = val

        if collection_vars:
            for key, val in collection_vars.items():
                # Handle VariableDefinition structure
                if isinstance(val, dict) and "value" in val:
                    context[key] = val["value"]
                else:
                    context[key] = val

        if runtime_vars:
            context.update(runtime_vars)

        if extracted_vars:
            context.update(extracted_vars)

        return context
