"""OpenAPI/Swagger specification importer."""

import json
import uuid
from typing import Any

import yaml


class OpenAPIImporter:
    """
    Import OpenAPI 3.x / Swagger 2.x specifications into API testing models.

    Generates test requests for each endpoint with example data and
    basic assertions based on documented responses.
    """

    def import_spec(
        self,
        spec_data: dict | str,
        user_id: str | None = None,
        org_id: str | None = None,
        generate_assertions: bool = True,
    ) -> tuple[dict, list[dict]]:
        """
        Import an OpenAPI specification.

        Args:
            spec_data: OpenAPI spec (dict, JSON string, or YAML string)
            user_id: Optional user ID for tenant
            org_id: Optional org ID for tenant
            generate_assertions: Whether to generate assertions from responses

        Returns:
            Tuple of (collection_dict, list_of_request_dicts)
        """
        # Parse spec
        if isinstance(spec_data, str):
            try:
                spec_data = json.loads(spec_data)
            except json.JSONDecodeError:
                spec_data = yaml.safe_load(spec_data)

        # Determine spec version
        is_openapi3 = spec_data.get("openapi", "").startswith("3.")
        is_swagger2 = spec_data.get("swagger", "").startswith("2.")

        if not (is_openapi3 or is_swagger2):
            raise ValueError("Unsupported specification version")

        # Build collection
        collection_id = str(uuid.uuid4())
        info = spec_data.get("info", {})

        # Get base URL
        if is_openapi3:
            servers = spec_data.get("servers", [])
            base_url = servers[0].get("url", "") if servers else ""
        else:
            # Swagger 2.x
            host = spec_data.get("host", "")
            base_path = spec_data.get("basePath", "")
            schemes = spec_data.get("schemes", ["https"])
            base_url = f"{schemes[0]}://{host}{base_path}" if host else ""

        collection = {
            "id": collection_id,
            "name": info.get("title", "Imported API"),
            "description": info.get("description", ""),
            "base_url": base_url,
            "auth_config": self._extract_security(spec_data),
            "variables": {},
            "default_headers": {"Content-Type": "application/json"},
            "default_engine": "python",
            "import_source": "openapi",
            "import_source_id": None,
            "user_id": user_id,
            "org_id": org_id,
        }

        # Extract requests from paths
        requests = []
        paths = spec_data.get("paths", {})

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                if method in path_item:
                    operation = path_item[method]
                    request = self._convert_operation(
                        path=path,
                        method=method.upper(),
                        operation=operation,
                        collection_id=collection_id,
                        order_index=len(requests),
                        spec_data=spec_data,
                        generate_assertions=generate_assertions,
                    )
                    requests.append(request)

        return collection, requests

    def _convert_operation(
        self,
        path: str,
        method: str,
        operation: dict,
        collection_id: str,
        order_index: int,
        spec_data: dict,
        generate_assertions: bool,
    ) -> dict:
        """Convert an OpenAPI operation to request format."""
        # Build name from operationId or path+method
        name = operation.get("operationId") or f"{method} {path}"

        # Extract parameters
        params = operation.get("parameters", [])
        query_params = {}
        headers = {}
        path_params = {}

        for param in params:
            param_in = param.get("in")
            param_name = param.get("name", "")

            # Get example or default value
            example = param.get("example") or param.get("default") or f"{{{{{param_name}}}}}"

            if param_in == "query":
                query_params[param_name] = str(example)
            elif param_in == "header":
                headers[param_name] = str(example)
            elif param_in == "path":
                path_params[param_name] = str(example)

        # Replace path parameters
        url_path = path
        for param_name, value in path_params.items():
            url_path = url_path.replace(f"{{{param_name}}}", f"{{{{{param_name}}}}}")

        # Build request body
        body = None
        if "requestBody" in operation:
            body = self._extract_request_body(operation["requestBody"], spec_data)
        elif "body" in [p.get("in") for p in params]:
            # Swagger 2.x body parameter
            for param in params:
                if param.get("in") == "body":
                    body = self._extract_schema_example(param.get("schema", {}), spec_data)
                    break

        # Generate assertions from responses
        assertions = []
        if generate_assertions:
            responses = operation.get("responses", {})
            assertions = self._generate_assertions(responses, spec_data)

        # Determine folder from tags
        tags = operation.get("tags", [])
        folder_path = tags[0] if tags else ""

        return {
            "id": str(uuid.uuid4()),
            "collection_id": collection_id,
            "name": name,
            "description": operation.get("summary", "") or operation.get("description", ""),
            "order_index": order_index,
            "method": method,
            "url_path": url_path,
            "headers": headers,
            "query_params": query_params,
            "body": body,
            "assertions": assertions,
            "variable_extractions": [],
            "folder_path": folder_path,
        }

    def _extract_request_body(self, request_body: dict, spec_data: dict) -> dict | None:
        """Extract request body from OpenAPI 3.x requestBody."""
        content = request_body.get("content", {})

        # Prefer JSON
        if "application/json" in content:
            schema = content["application/json"].get("schema", {})
            example = content["application/json"].get("example")

            if example:
                return {"type": "json", "content": example}

            # Generate from schema
            generated = self._extract_schema_example(schema, spec_data)
            if generated:
                return {"type": "json", "content": generated}

        # Try form data
        if "application/x-www-form-urlencoded" in content:
            schema = content["application/x-www-form-urlencoded"].get("schema", {})
            form_data = self._schema_to_form(schema, spec_data)
            if form_data:
                return {"type": "form", "content": form_data}

        return None

    def _extract_schema_example(self, schema: dict, spec_data: dict) -> Any:
        """Generate example data from JSON Schema."""
        # Resolve $ref if present
        if "$ref" in schema:
            schema = self._resolve_ref(schema["$ref"], spec_data)

        # Check for example
        if "example" in schema:
            return schema["example"]

        schema_type = schema.get("type", "object")

        if schema_type == "object":
            result = {}
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                result[prop_name] = self._extract_schema_example(prop_schema, spec_data)
            return result

        elif schema_type == "array":
            items = schema.get("items", {})
            return [self._extract_schema_example(items, spec_data)]

        elif schema_type == "string":
            return schema.get("default", "string")

        elif schema_type == "integer":
            return schema.get("default", 0)

        elif schema_type == "number":
            return schema.get("default", 0.0)

        elif schema_type == "boolean":
            return schema.get("default", True)

        return None

    def _schema_to_form(self, schema: dict, spec_data: dict) -> dict:
        """Convert schema to form data dict."""
        if "$ref" in schema:
            schema = self._resolve_ref(schema["$ref"], spec_data)

        result = {}
        properties = schema.get("properties", {})

        for prop_name, prop_schema in properties.items():
            example = prop_schema.get("example") or prop_schema.get("default")
            if example:
                result[prop_name] = str(example)
            else:
                prop_type = prop_schema.get("type", "string")
                if prop_type == "string":
                    result[prop_name] = ""
                elif prop_type in ("integer", "number"):
                    result[prop_name] = "0"
                elif prop_type == "boolean":
                    result[prop_name] = "true"

        return result

    def _resolve_ref(self, ref: str, spec_data: dict) -> dict:
        """Resolve a $ref pointer."""
        if not ref.startswith("#/"):
            return {}

        parts = ref[2:].split("/")
        current = spec_data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return {}

        return current if isinstance(current, dict) else {}

    def _generate_assertions(self, responses: dict, spec_data: dict) -> list[dict]:
        """Generate assertions from documented responses."""
        assertions = []

        # Check for success response (2xx)
        success_codes = ["200", "201", "202", "204"]
        for code in success_codes:
            if code in responses:
                assertions.append({
                    "type": "status",
                    "name": f"Status {code}",
                    "config": {"expected": int(code), "operator": "equals"},
                })
                break

        # If no specific success code, check for 2xx range
        if not assertions:
            assertions.append({
                "type": "status",
                "name": "Success status",
                "config": {"expected": [200, 299], "operator": "range"},
            })

        # Check response schema for required fields
        if "200" in responses:
            response_200 = responses["200"]
            content = response_200.get("content", {})

            if "application/json" in content:
                schema = content["application/json"].get("schema", {})
                if "$ref" in schema:
                    schema = self._resolve_ref(schema["$ref"], spec_data)

                # Add assertions for required properties
                required = schema.get("required", [])
                for prop in required[:3]:  # Limit to first 3 required fields
                    assertions.append({
                        "type": "jsonpath",
                        "name": f"Check {prop} exists",
                        "config": {"path": f"$.{prop}", "operator": "exists"},
                    })

        return assertions

    def _extract_security(self, spec_data: dict) -> dict | None:
        """Extract security configuration from spec."""
        security_defs = spec_data.get("securityDefinitions", {})  # Swagger 2
        components = spec_data.get("components", {})
        security_schemes = components.get("securitySchemes", {})  # OpenAPI 3

        schemes = security_defs or security_schemes

        for name, scheme in schemes.items():
            scheme_type = scheme.get("type")

            if scheme_type == "http" and scheme.get("scheme") == "bearer":
                return {
                    "type": "bearer",
                    "config": {"token": "{{auth_token}}"},
                }

            elif scheme_type == "http" and scheme.get("scheme") == "basic":
                return {
                    "type": "basic",
                    "config": {"username": "{{username}}", "password": "{{password}}"},
                }

            elif scheme_type == "apiKey":
                return {
                    "type": "api_key",
                    "config": {
                        "key": scheme.get("name", ""),
                        "value": "{{api_key}}",
                        "in": scheme.get("in", "header"),
                    },
                }

        return None
