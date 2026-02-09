"""Converter between Python API requests and Karate .feature files."""

import json
import re
from typing import Any


class KarateConverter:
    """
    Converts between Python API request format and Karate .feature format.

    Supports:
    - Converting APIRequest objects to Karate scenarios
    - Converting collections to complete .feature files
    - Parsing .feature files back to APIRequest format
    """

    def requests_to_feature(
        self,
        requests: list[dict],
        collection: dict,
        feature_name: str | None = None,
        include_background: bool = True,
        capture_http_details: bool = True,
    ) -> str:
        """
        Convert a list of API requests to a Karate .feature file.

        Args:
            requests: List of APIRequest-like dicts
            collection: APICollection-like dict with base_url, auth_config, etc.
            feature_name: Optional feature name (defaults to collection name)
            include_background: Whether to include Background section
            capture_http_details: Whether to inject hooks to capture HTTP request/response

        Returns:
            Complete .feature file content
        """
        lines = []

        # Feature header
        name = feature_name or collection.get("name", "API Tests")
        lines.append(f"Feature: {name}")
        lines.append("")

        if collection.get("description"):
            # Add description as feature description
            for line in collection["description"].split("\n"):
                lines.append(f"  {line}")
            lines.append("")

        # Background section for common setup
        if include_background and (collection.get("base_url") or collection.get("auth_config") or capture_http_details):
            lines.append("  Background:")

            # Initialize HTTP capture array if enabled
            if capture_http_details:
                lines.append("    * def httpCaptures = karate.get('httpCaptures') || []")

            # Base URL
            if collection.get("base_url"):
                base_url = collection["base_url"]
                lines.append(f"    * url '{base_url}'")

            # Auth configuration
            if collection.get("auth_config"):
                auth_lines = self._auth_config_to_karate(collection["auth_config"])
                lines.extend(f"    {line}" for line in auth_lines)

            # Default headers
            if collection.get("default_headers"):
                for key, value in collection["default_headers"].items():
                    lines.append(f"    * header {key} = '{value}'")

            lines.append("")

        # Convert each request to a scenario
        for request in requests:
            scenario_lines = self._request_to_scenario(request, collection, capture_http_details)
            lines.extend(scenario_lines)
            lines.append("")

        # Add a final scenario to write HTTP captures to file
        if capture_http_details:
            lines.append("  @http-capture-output")
            lines.append("  Scenario: Write HTTP Captures to File")
            lines.append("    * def httpCaptures = karate.get('httpCaptures') || []")
            lines.append("    * def outputPath = karate.properties['karate.output.dir'] || '.'")
            lines.append("    * def filePath = outputPath + '/http-captures.json'")
            lines.append("    * def jsonString = karate.toJson(httpCaptures)")
            lines.append("    * karate.write(jsonString, filePath)")
            lines.append("")

        return "\n".join(lines)

    def _request_to_scenario(self, request: dict, collection: dict, capture_http_details: bool = True) -> list[str]:
        """Convert a single request to a Karate scenario."""
        lines = []

        # Scenario header with optional tags
        name = request.get("name", "API Request")
        folder = request.get("folder_path", "")

        # Add tags based on method and folder
        tags = []
        method = request.get("method", "GET")
        tags.append(f"@{method.lower()}")
        if folder:
            # Convert folder path to tag
            tag = folder.replace("/", "_").replace(" ", "_").lower()
            tags.append(f"@{tag}")

        if tags:
            lines.append(f"  {' '.join(tags)}")

        lines.append(f"  Scenario: {name}")

        # Description as comment
        if request.get("description"):
            lines.append(f"    # {request['description']}")

        # Path
        url_path = request.get("url_path", "/")
        # Handle variables: convert {{var}} to karate syntax
        url_path = self._convert_variables_to_karate(url_path)
        lines.append(f"    Given path '{url_path}'")

        # Query parameters
        if request.get("query_params"):
            for key, value in request["query_params"].items():
                value = self._convert_variables_to_karate(str(value))
                lines.append(f"    And param {key} = '{value}'")

        # Headers
        if request.get("headers"):
            for key, value in request["headers"].items():
                value = self._convert_variables_to_karate(str(value))
                lines.append(f"    And header {key} = '{value}'")

        # Request body
        if request.get("body"):
            body_config = request["body"]
            body_type = body_config.get("type", "none")
            content = body_config.get("content")

            if body_type == "json" and content:
                # Format JSON nicely
                json_str = json.dumps(content, indent=6)
                # Convert {{var}} to #(var)
                json_str = self._convert_variables_to_karate(json_str)
                lines.append("    And request")
                lines.append('    """')
                for json_line in json_str.split("\n"):
                    lines.append(f"    {json_line}")
                lines.append('    """')

            elif body_type == "form" and content:
                for key, value in content.items():
                    value = self._convert_variables_to_karate(str(value))
                    lines.append(f"    And form field {key} = '{value}'")

            elif body_type == "raw" and content:
                content = self._convert_variables_to_karate(str(content))
                lines.append(f"    And request '{content}'")

            elif body_type == "graphql" and content:
                query = content.get("query", "")
                variables = content.get("variables", {})
                gql_body = {"query": query, "variables": variables}
                json_str = json.dumps(gql_body, indent=6)
                json_str = self._convert_variables_to_karate(json_str)
                lines.append("    And request")
                lines.append('    """')
                for json_line in json_str.split("\n"):
                    lines.append(f"    {json_line}")
                lines.append('    """')

        # HTTP method
        lines.append(f"    When method {method.lower()}")

        # Capture HTTP details for payload visibility (Karate uses list + [item] to append)
        if capture_http_details:
            scenario_name_escaped = name.replace("'", "\\'")
            lines.append(f"    * def captureData = {{ scenarioName: '{scenario_name_escaped}', request: karate.prevRequest, response: {{ status: responseStatus, headers: responseHeaders, body: response, time: responseTime }} }}")
            lines.append("    * def httpCaptures = httpCaptures + [captureData]")
            lines.append("    * karate.set('httpCaptures', httpCaptures)")

        # Assertions
        if request.get("assertions"):
            for assertion in request["assertions"]:
                assertion_lines = self._assertion_to_karate(assertion)
                lines.extend(f"    {line}" for line in assertion_lines)

        # Variable extractions
        if request.get("variable_extractions"):
            for extraction in request["variable_extractions"]:
                extraction_line = self._extraction_to_karate(extraction)
                if extraction_line:
                    lines.append(f"    {extraction_line}")

        return lines

    def _auth_config_to_karate(self, auth_config: dict) -> list[str]:
        """Convert auth configuration to Karate steps."""
        lines = []
        auth_type = auth_config.get("type", "none")
        config = auth_config.get("config", {})

        if auth_type == "bearer":
            token = config.get("token", "")
            token = self._convert_variables_to_karate(token)
            lines.append(f"* header Authorization = 'Bearer ' + {token}")

        elif auth_type == "basic":
            username = self._convert_variables_to_karate(config.get("username", ""))
            password = self._convert_variables_to_karate(config.get("password", ""))
            # Karate has built-in basic auth
            lines.append(f"* configure headers = {{ Authorization: 'Basic ' + karate.toBase64({username} + ':' + {password}) }}")

        elif auth_type == "api_key":
            key = config.get("key", "")
            value = self._convert_variables_to_karate(config.get("value", ""))
            location = config.get("in", "header")
            if location == "header":
                lines.append(f"* header {key} = {value}")

        return lines

    def _assertion_to_karate(self, assertion: dict) -> list[str]:
        """Convert an assertion to Karate match statements."""
        lines = []
        assertion_type = assertion.get("type")
        config = assertion.get("config", {})

        if assertion_type == "status":
            expected = config.get("expected")
            operator = config.get("operator", "equals")

            if operator == "equals":
                lines.append(f"Then status {expected}")
            elif operator == "in":
                # Handle list of status codes
                if isinstance(expected, list):
                    conditions = " || ".join(f"responseStatus == {s}" for s in expected)
                    lines.append(f"Then assert {conditions}")
                else:
                    lines.append(f"Then status {expected}")
            elif operator == "range":
                if isinstance(expected, list) and len(expected) == 2:
                    lines.append(f"Then assert responseStatus >= {expected[0]} && responseStatus <= {expected[1]}")

        elif assertion_type == "jsonpath":
            path = config.get("path", "$")
            expected = config.get("expected")
            operator = config.get("operator", "equals")

            # Convert JSONPath to Karate path syntax
            karate_path = self._jsonpath_to_karate(path)

            if operator == "exists":
                lines.append(f"And match {karate_path} == '#present'")
            elif operator == "not_exists":
                lines.append(f"And match {karate_path} == '#notpresent'")
            elif operator == "equals":
                if isinstance(expected, str):
                    lines.append(f"And match {karate_path} == '{expected}'")
                else:
                    lines.append(f"And match {karate_path} == {json.dumps(expected)}")
            elif operator == "contains":
                lines.append(f"And match {karate_path} contains '{expected}'")
            elif operator == "not_equals":
                if isinstance(expected, str):
                    lines.append(f"And match {karate_path} != '{expected}'")
                else:
                    lines.append(f"And match {karate_path} != {json.dumps(expected)}")

        elif assertion_type == "header":
            name = config.get("name", "")
            expected = config.get("expected")
            operator = config.get("operator", "exists")

            if operator == "exists":
                lines.append(f"And match responseHeaders['{name}'] == '#present'")
            elif operator == "equals":
                lines.append(f"And match responseHeaders['{name}'][0] == '{expected}'")
            elif operator == "contains":
                lines.append(f"And match responseHeaders['{name}'][0] contains '{expected}'")

        elif assertion_type == "timing":
            max_ms = config.get("max_ms")
            lines.append(f"And assert responseTime < {max_ms}")

        elif assertion_type == "body_contains":
            expected = config.get("expected", "")
            lines.append(f"And match response contains '{expected}'")

        elif assertion_type == "schema":
            schema = config.get("schema", {})
            # Karate has built-in schema validation
            schema_str = json.dumps(schema)
            lines.append(f"And match response == '#({schema_str})'")

        return lines

    def _extraction_to_karate(self, extraction: dict) -> str | None:
        """Convert variable extraction to Karate def statement."""
        name = extraction.get("name")
        source = extraction.get("source", "jsonpath")
        path = extraction.get("path", "")

        if not name:
            return None

        if source == "jsonpath":
            karate_path = self._jsonpath_to_karate(path)
            return f"* def {name} = {karate_path}"
        elif source == "header":
            return f"* def {name} = responseHeaders['{path}'][0]"
        elif source == "status":
            return f"* def {name} = responseStatus"
        elif source == "body":
            return f"* def {name} = response"

        return None

    def _convert_variables_to_karate(self, text: str) -> str:
        """Convert {{variable}} syntax to Karate #(variable) syntax."""
        # Simple variables: {{var}} -> #(var)
        text = re.sub(r'\{\{(\w+)\}\}', r'#(\1)', text)
        # Nested paths: {{var.path}} -> #(var.path)
        text = re.sub(r'\{\{([\w.]+)\}\}', r'#(\1)', text)
        return text

    def _jsonpath_to_karate(self, jsonpath: str) -> str:
        """
        Convert JSONPath to Karate path syntax.

        JSONPath: $.data.items[0].name
        Karate:   response.data.items[0].name
        """
        path = jsonpath
        # Remove leading $
        if path.startswith("$."):
            path = path[2:]
        elif path.startswith("$"):
            path = path[1:]

        # Add response prefix
        return f"response.{path}" if path else "response"

    def feature_to_requests(
        self,
        feature_content: str,
        collection_id: str | None = None,
    ) -> tuple[dict, list[dict]]:
        """
        Parse a Karate .feature file into collection and request dicts.

        Args:
            feature_content: Content of .feature file
            collection_id: Optional collection ID to assign

        Returns:
            Tuple of (collection_dict, list_of_request_dicts)

        Note: This is a simplified parser. Full Gherkin parsing would require
        a dedicated library like gherkin-official.
        """
        lines = feature_content.split("\n")

        collection = {
            "id": collection_id,
            "name": "Imported Feature",
            "description": "",
            "base_url": "",
            "variables": {},
            "default_headers": {},
        }

        requests = []
        current_scenario = None
        in_background = False
        in_docstring = False
        docstring_content = []

        for line in lines:
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue

            # Feature name
            if stripped.startswith("Feature:"):
                collection["name"] = stripped[8:].strip()
                continue

            # Background section
            if stripped.startswith("Background:"):
                in_background = True
                continue

            # Scenario starts
            if stripped.startswith("Scenario:") or stripped.startswith("Scenario Outline:"):
                in_background = False
                if current_scenario:
                    requests.append(current_scenario)

                current_scenario = {
                    "name": stripped.split(":", 1)[1].strip(),
                    "method": "GET",
                    "url_path": "/",
                    "headers": {},
                    "body": None,
                    "assertions": [],
                    "variable_extractions": [],
                }
                continue

            # Handle docstrings
            if stripped == '"""':
                if in_docstring:
                    # End of docstring
                    in_docstring = False
                    if current_scenario and docstring_content:
                        # Try to parse as JSON body
                        try:
                            content = "\n".join(docstring_content)
                            json_content = json.loads(content)
                            current_scenario["body"] = {
                                "type": "json",
                                "content": json_content,
                            }
                        except json.JSONDecodeError:
                            current_scenario["body"] = {
                                "type": "raw",
                                "content": "\n".join(docstring_content),
                            }
                    docstring_content = []
                else:
                    in_docstring = True
                continue

            if in_docstring:
                docstring_content.append(stripped)
                continue

            # Parse Karate steps
            if in_background:
                self._parse_background_step(stripped, collection)
            elif current_scenario:
                self._parse_scenario_step(stripped, current_scenario)

        # Don't forget last scenario
        if current_scenario:
            requests.append(current_scenario)

        return collection, requests

    def _parse_background_step(self, line: str, collection: dict):
        """Parse a Background step and update collection."""
        # Remove step keyword
        for keyword in ["* ", "Given ", "And ", "When ", "Then "]:
            if line.startswith(keyword):
                line = line[len(keyword):]
                break

        # URL
        if line.startswith("url "):
            url = line[4:].strip().strip("'\"")
            collection["base_url"] = url

        # Header
        elif line.startswith("header "):
            # header Name = 'value'
            match = re.match(r"header\s+(\S+)\s*=\s*['\"]?(.+?)['\"]?$", line)
            if match:
                collection["default_headers"][match.group(1)] = match.group(2)

    def _parse_scenario_step(self, line: str, scenario: dict):
        """Parse a Scenario step and update request."""
        # Remove step keyword
        for keyword in ["* ", "Given ", "And ", "When ", "Then "]:
            if line.startswith(keyword):
                line = line[len(keyword):]
                break

        # Path
        if line.startswith("path "):
            path = line[5:].strip().strip("'\"")
            scenario["url_path"] = self._convert_karate_to_variables(path)

        # Method
        elif line.startswith("method "):
            method = line[7:].strip().upper()
            scenario["method"] = method

        # Header
        elif line.startswith("header "):
            match = re.match(r"header\s+(\S+)\s*=\s*['\"]?(.+?)['\"]?$", line)
            if match:
                scenario["headers"][match.group(1)] = self._convert_karate_to_variables(match.group(2))

        # Param
        elif line.startswith("param "):
            match = re.match(r"param\s+(\S+)\s*=\s*['\"]?(.+?)['\"]?$", line)
            if match:
                if "query_params" not in scenario:
                    scenario["query_params"] = {}
                scenario["query_params"][match.group(1)] = self._convert_karate_to_variables(match.group(2))

        # Status assertion
        elif line.startswith("status "):
            status = int(line[7:].strip())
            scenario["assertions"].append({
                "type": "status",
                "config": {"expected": status, "operator": "equals"},
            })

        # Match assertion
        elif line.startswith("match "):
            # Simplified match parsing
            if "==" in line:
                parts = line[6:].split("==", 1)
                if len(parts) == 2:
                    path = parts[0].strip()
                    expected = parts[1].strip().strip("'\"")

                    # Convert Karate path to JSONPath
                    if path.startswith("response."):
                        jsonpath = "$." + path[9:]
                    elif path == "response":
                        jsonpath = "$"
                    else:
                        jsonpath = "$." + path

                    scenario["assertions"].append({
                        "type": "jsonpath",
                        "config": {
                            "path": jsonpath,
                            "expected": expected,
                            "operator": "equals",
                        },
                    })

        # Variable definition (extraction)
        elif line.startswith("def "):
            match = re.match(r"def\s+(\w+)\s*=\s*(.+)$", line)
            if match:
                var_name = match.group(1)
                var_expr = match.group(2).strip()

                if var_expr.startswith("response."):
                    # JSONPath extraction
                    jsonpath = "$." + var_expr[9:]
                    scenario["variable_extractions"].append({
                        "name": var_name,
                        "source": "jsonpath",
                        "path": jsonpath,
                    })
                elif var_expr == "responseStatus":
                    scenario["variable_extractions"].append({
                        "name": var_name,
                        "source": "status",
                        "path": "",
                    })

    def _convert_karate_to_variables(self, text: str) -> str:
        """Convert Karate #(variable) syntax to {{variable}} syntax."""
        return re.sub(r'#\((\w+)\)', r'{{\1}}', text)
