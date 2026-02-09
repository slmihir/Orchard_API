"""Postman Collection v2.1 importer."""

import json
import uuid
from typing import Any


class PostmanImporter:
    """
    Import Postman Collection v2.1 format into API testing models.

    Postman Collection Structure:
    {
        "info": {"name": "...", "schema": "..."},
        "item": [
            {
                "name": "Folder or Request",
                "item": [...],  # If folder
                "request": {...},  # If request
                "response": [...]
            }
        ],
        "variable": [...],
        "auth": {...}
    }
    """

    def import_collection(
        self,
        collection_data: dict | str,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> tuple[dict, list[dict], list[dict]]:
        """
        Import a Postman collection.

        Args:
            collection_data: Postman collection JSON (dict or string)
            user_id: Optional user ID for tenant
            org_id: Optional org ID for tenant

        Returns:
            Tuple of (collection_dict, list_of_request_dicts, list_of_environment_dicts)
        """
        if isinstance(collection_data, str):
            collection_data = json.loads(collection_data)

        info = collection_data.get("info", {})
        items = collection_data.get("item", [])
        variables = collection_data.get("variable", [])
        auth = collection_data.get("auth")

        # Build collection
        collection_id = str(uuid.uuid4())
        collection = {
            "id": collection_id,
            "name": info.get("name", "Imported Collection"),
            "description": info.get("description", ""),
            "base_url": self._extract_base_url(variables),
            "auth_config": self._convert_auth(auth) if auth else None,
            "variables": self._convert_variables(variables),
            "default_headers": {},
            "default_engine": "python",
            "import_source": "postman",
            "import_source_id": info.get("_postman_id"),
            "user_id": user_id,
            "org_id": org_id,
        }

        # Extract requests (recursively through folders)
        requests = []
        self._extract_requests(items, requests, collection_id, folder_path="")

        # Convert Postman environments if present
        environments = []
        # Note: Postman environments are separate files, not in collection

        return collection, requests, environments

    def _extract_requests(
        self,
        items: list,
        requests: list,
        collection_id: str,
        folder_path: str,
    ):
        """Recursively extract requests from items."""
        for idx, item in enumerate(items):
            if "item" in item:
                # This is a folder
                new_folder = f"{folder_path}/{item.get('name', 'Folder')}" if folder_path else item.get("name", "Folder")
                self._extract_requests(item["item"], requests, collection_id, new_folder)
            elif "request" in item:
                # This is a request
                request = self._convert_request(item, collection_id, folder_path, len(requests))
                requests.append(request)

    def _convert_request(
        self,
        item: dict,
        collection_id: str,
        folder_path: str,
        order_index: int,
    ) -> dict:
        """Convert a Postman request to our format."""
        request_data = item.get("request", {})

        # Handle string request (just URL)
        if isinstance(request_data, str):
            return {
                "id": str(uuid.uuid4()),
                "collection_id": collection_id,
                "name": item.get("name", "Request"),
                "description": "",
                "order_index": order_index,
                "method": "GET",
                "url_path": request_data,
                "headers": {},
                "query_params": {},
                "body": None,
                "assertions": [],
                "variable_extractions": [],
                "folder_path": folder_path,
            }

        # Get URL
        url = request_data.get("url", {})
        if isinstance(url, str):
            url_path = url
            query_params = {}
        else:
            url_path = self._build_url_path(url)
            query_params = self._extract_query_params(url)

        # Get headers
        headers = {}
        for header in request_data.get("header", []):
            if not header.get("disabled"):
                headers[header.get("key", "")] = header.get("value", "")

        # Get body
        body = self._convert_body(request_data.get("body"))

        # Convert tests to assertions
        assertions = self._convert_tests(item.get("event", []))

        return {
            "id": str(uuid.uuid4()),
            "collection_id": collection_id,
            "name": item.get("name", "Request"),
            "description": request_data.get("description", ""),
            "order_index": order_index,
            "method": request_data.get("method", "GET"),
            "url_path": url_path,
            "headers": headers,
            "query_params": query_params,
            "body": body,
            "assertions": assertions,
            "variable_extractions": [],
            "folder_path": folder_path,
        }

    def _build_url_path(self, url: dict) -> str:
        """Build URL path from Postman URL object."""
        path = url.get("path", [])
        if isinstance(path, list):
            return "/" + "/".join(path)
        return path or "/"

    def _extract_query_params(self, url: dict) -> dict:
        """Extract query parameters from Postman URL object."""
        params = {}
        for query in url.get("query", []):
            if not query.get("disabled"):
                params[query.get("key", "")] = query.get("value", "")
        return params

    def _convert_body(self, body: dict | None) -> dict | None:
        """Convert Postman body to our format."""
        if not body:
            return None

        mode = body.get("mode")

        if mode == "raw":
            raw = body.get("raw", "")
            options = body.get("options", {}).get("raw", {})
            language = options.get("language", "text")

            if language == "json":
                try:
                    content = json.loads(raw)
                    return {"type": "json", "content": content}
                except json.JSONDecodeError:
                    return {"type": "raw", "content": raw}
            else:
                return {"type": "raw", "content": raw}

        elif mode == "urlencoded":
            content = {}
            for item in body.get("urlencoded", []):
                if not item.get("disabled"):
                    content[item.get("key", "")] = item.get("value", "")
            return {"type": "form", "content": content}

        elif mode == "formdata":
            content = {}
            for item in body.get("formdata", []):
                if not item.get("disabled"):
                    content[item.get("key", "")] = item.get("value", "")
            return {"type": "form", "content": content}

        elif mode == "graphql":
            graphql = body.get("graphql", {})
            return {
                "type": "graphql",
                "content": {
                    "query": graphql.get("query", ""),
                    "variables": json.loads(graphql.get("variables", "{}")) if graphql.get("variables") else {},
                },
            }

        return None

    def _convert_auth(self, auth: dict) -> dict | None:
        """Convert Postman auth to our format."""
        auth_type = auth.get("type")

        if auth_type == "bearer":
            bearer = auth.get("bearer", [])
            token = self._find_auth_value(bearer, "token")
            return {
                "type": "bearer",
                "config": {"token": token},
            }

        elif auth_type == "basic":
            basic = auth.get("basic", [])
            username = self._find_auth_value(basic, "username")
            password = self._find_auth_value(basic, "password")
            return {
                "type": "basic",
                "config": {"username": username, "password": password},
            }

        elif auth_type == "apikey":
            apikey = auth.get("apikey", [])
            key = self._find_auth_value(apikey, "key")
            value = self._find_auth_value(apikey, "value")
            location = self._find_auth_value(apikey, "in") or "header"
            return {
                "type": "api_key",
                "config": {"key": key, "value": value, "in": location},
            }

        return None

    def _find_auth_value(self, auth_list: list, key: str) -> str:
        """Find value in Postman auth array."""
        for item in auth_list:
            if item.get("key") == key:
                return item.get("value", "")
        return ""

    def _convert_variables(self, variables: list) -> dict:
        """Convert Postman variables to our format."""
        result = {}
        for var in variables:
            name = var.get("key", "")
            if name:
                result[name] = {
                    "value": var.get("value", ""),
                    "type": "string",
                }
        return result

    def _extract_base_url(self, variables: list) -> str:
        """Try to extract base URL from variables."""
        for var in variables:
            key = var.get("key", "").lower()
            if key in ("baseurl", "base_url", "host", "url"):
                return var.get("value", "")
        return ""

    def _convert_tests(self, events: list) -> list[dict]:
        """Convert Postman test scripts to assertions."""
        assertions = []

        for event in events:
            if event.get("listen") == "test":
                script = event.get("script", {})
                exec_lines = script.get("exec", [])

                for line in exec_lines:
                    # Try to parse common Postman test patterns
                    assertions.extend(self._parse_test_line(line))

        return assertions

    def _parse_test_line(self, line: str) -> list[dict]:
        """Parse a Postman test script line into assertions."""
        assertions = []

        # pm.response.to.have.status(200)
        if "pm.response.to.have.status" in line:
            import re
            match = re.search(r'status\((\d+)\)', line)
            if match:
                assertions.append({
                    "type": "status",
                    "name": "Status code check",
                    "config": {"expected": int(match.group(1)), "operator": "equals"},
                })

        # pm.expect(jsonData.field).to.eql(value)
        elif "pm.expect" in line and ".to.eql" in line:
            import re
            match = re.search(r'pm\.expect\(jsonData\.(\w+)\)\.to\.eql\(["\']?([^"\']+)["\']?\)', line)
            if match:
                assertions.append({
                    "type": "jsonpath",
                    "name": f"Check {match.group(1)}",
                    "config": {
                        "path": f"$.{match.group(1)}",
                        "expected": match.group(2),
                        "operator": "equals",
                    },
                })

        return assertions


def import_postman_environment(env_data: dict | str) -> dict:
    """
    Import a Postman environment file.

    Args:
        env_data: Postman environment JSON

    Returns:
        APIEnvironment-compatible dict
    """
    if isinstance(env_data, str):
        env_data = json.loads(env_data)

    variables = {}
    for var in env_data.get("values", []):
        if var.get("enabled", True):
            variables[var.get("key", "")] = {
                "value": var.get("value", ""),
                "type": "string",
                "secret": var.get("type") == "secret",
            }

    return {
        "id": str(uuid.uuid4()),
        "name": env_data.get("name", "Imported Environment"),
        "description": "",
        "variables": variables,
        "is_default": False,
    }
