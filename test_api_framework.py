#!/usr/bin/env python3
"""
End-to-end test for the API Testing Framework.
Tests: Collection CRUD, Request CRUD, Execution, Environment management.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log_pass(msg):
    print(f"{GREEN}✓ {msg}{RESET}")

def log_fail(msg):
    print(f"{RED}✗ {msg}{RESET}")

def log_info(msg):
    print(f"{YELLOW}→ {msg}{RESET}")

def get_auth_token():
    """Register a test user and get auth token."""
    # Try to register
    register_data = {
        "email": "apitest@example.com",
        "password": "testpass123",
        "name": "API Test User"
    }
    resp = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
    if resp.status_code == 201:
        # Registration succeeded, token is in response
        return resp.json().get("access_token")

    # Login (works whether registration succeeded or user already exists)
    login_data = {"username": "apitest@example.com", "password": "testpass123"}
    resp = requests.post(f"{BASE_URL}/api/auth/login", data=login_data)

    if resp.status_code == 200:
        return resp.json()["access_token"]
    else:
        print(f"Login failed: {resp.status_code} - {resp.text}")
        return None

def main():
    print("\n" + "="*60)
    print("  API Testing Framework - End-to-End Test")
    print("="*60 + "\n")

    # Get auth token
    log_info("Getting auth token...")
    token = get_auth_token()
    if not token:
        log_fail("Could not authenticate. Make sure the backend is running.")
        sys.exit(1)
    log_pass("Authenticated successfully")

    headers = {"Authorization": f"Bearer {token}"}

    collection_id = None
    request_id = None
    environment_id = None
    run_id = None

    try:
        # 1. Create Collection
        print("\n--- Test 1: Create Collection ---")
        collection_data = {
            "name": "E2E Test Collection",
            "description": "Testing the API framework",
            "base_url": "https://httpbin.org",
            "variables": {"test_var": {"value": "hello", "type": "string"}}
        }
        resp = requests.post(f"{BASE_URL}/api/api-collections", json=collection_data, headers=headers)
        if resp.status_code == 201:
            collection_id = resp.json()["id"]
            log_pass(f"Collection created: {collection_id}")
        else:
            log_fail(f"Create collection failed: {resp.status_code} - {resp.text}")
            sys.exit(1)

        # 2. List Collections
        print("\n--- Test 2: List Collections ---")
        resp = requests.get(f"{BASE_URL}/api/api-collections", headers=headers)
        if resp.status_code == 200:
            collections = resp.json()
            log_pass(f"Listed {len(collections)} collection(s)")
        else:
            log_fail(f"List collections failed: {resp.status_code}")

        # 3. Create Request
        print("\n--- Test 3: Create API Request ---")
        request_data = {
            "collection_id": collection_id,
            "name": "Get IP Address",
            "method": "GET",
            "url": "/ip",
            "assertions": [
                {"type": "status", "config": {"expected": 200}},
                {"type": "jsonpath", "config": {"path": "$.origin", "operator": "exists"}}
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/api-requests", json=request_data, headers=headers)
        if resp.status_code == 201:
            request_id = resp.json()["id"]
            log_pass(f"Request created: {request_id}")
        else:
            log_fail(f"Create request failed: {resp.status_code} - {resp.text}")
            sys.exit(1)

        # 4. Create second request with POST
        print("\n--- Test 4: Create POST Request ---")
        request_data2 = {
            "collection_id": collection_id,
            "name": "Echo POST Data",
            "method": "POST",
            "url": "/post",
            "headers": {"Content-Type": "application/json"},
            "body": {"message": "{{test_var}}", "timestamp": "now"},
            "assertions": [
                {"type": "status", "config": {"expected": 200}},
                {"type": "jsonpath", "config": {"path": "$.json.message", "operator": "equals", "expected": "hello"}}
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/api-requests", json=request_data2, headers=headers)
        if resp.status_code == 201:
            request_id2 = resp.json()["id"]
            log_pass(f"POST Request created: {request_id2}")
        else:
            log_fail(f"Create POST request failed: {resp.status_code} - {resp.text}")

        # 5. Create Environment
        print("\n--- Test 5: Create Environment ---")
        env_data = {
            "name": "Production",
            "variables": {
                "test_var": {"value": "production_value", "type": "string"},
                "api_key": {"value": "secret123", "type": "string", "secret": True}
            }
        }
        resp = requests.post(f"{BASE_URL}/api/api-environments", json=env_data, headers=headers)
        if resp.status_code == 201:
            environment_id = resp.json()["id"]
            log_pass(f"Environment created: {environment_id}")
        else:
            log_fail(f"Create environment failed: {resp.status_code} - {resp.text}")

        # 6. Execute Single Request
        print("\n--- Test 6: Execute Single Request ---")
        resp = requests.post(
            f"{BASE_URL}/api/api-runs/execute/request/{request_id}",
            headers=headers
        )
        if resp.status_code == 200:
            result = resp.json()
            status = result.get("status", "unknown")
            log_pass(f"Request executed - Status: {status}")
            if result.get("assertions"):
                for a in result["assertions"]:
                    status_icon = "✓" if a.get("passed") else "✗"
                    print(f"    {status_icon} Assertion: {a.get('type')} - {a.get('message', 'OK')}")
        else:
            log_fail(f"Execute request failed: {resp.status_code} - {resp.text}")

        # 7. Execute Collection
        print("\n--- Test 7: Execute Collection ---")
        resp = requests.post(
            f"{BASE_URL}/api/api-runs/execute/collection/{collection_id}",
            headers=headers
        )
        if resp.status_code in [200, 201]:
            result = resp.json()
            run_id = result.get("id")
            log_pass(f"Collection executed - Run ID: {run_id}")
            log_info(f"  Total: {result.get('total_requests', 0)}, Passed: {result.get('passed_requests', 0)}, Failed: {result.get('failed_requests', 0)}")
        else:
            log_fail(f"Execute collection failed: {resp.status_code} - {resp.text}")

        # 8. List Runs
        print("\n--- Test 8: List Test Runs ---")
        resp = requests.get(f"{BASE_URL}/api/api-runs", headers=headers)
        if resp.status_code == 200:
            runs = resp.json()
            log_pass(f"Listed {len(runs)} test run(s)")
        else:
            log_fail(f"List runs failed: {resp.status_code}")

        # 9. Get Collection with requests
        print("\n--- Test 9: Get Collection Details ---")
        resp = requests.get(f"{BASE_URL}/api/api-collections/{collection_id}", headers=headers)
        if resp.status_code == 200:
            collection = resp.json()
            num_requests = len(collection.get("requests", []))
            log_pass(f"Collection has {num_requests} request(s)")
        else:
            log_fail(f"Get collection failed: {resp.status_code}")

        # 10. Export to Karate
        print("\n--- Test 10: Export to Karate Feature ---")
        resp = requests.get(f"{BASE_URL}/api/api-collections/{collection_id}/export/karate", headers=headers)
        if resp.status_code == 200:
            feature = resp.text
            log_pass("Karate feature file generated")
            print("    Preview (first 5 lines):")
            for line in feature.split('\n')[:5]:
                print(f"    | {line}")
        else:
            log_fail(f"Export to Karate failed: {resp.status_code} - {resp.text}")

        print("\n" + "="*60)
        print(f"  {GREEN}All tests completed!{RESET}")
        print("="*60 + "\n")

    finally:
        # Cleanup
        log_info("Cleaning up test data...")
        if run_id:
            requests.delete(f"{BASE_URL}/api/api-runs/{run_id}", headers=headers)
        if environment_id:
            requests.delete(f"{BASE_URL}/api/api-environments/{environment_id}", headers=headers)
        if collection_id:
            requests.delete(f"{BASE_URL}/api/api-collections/{collection_id}", headers=headers)
        log_pass("Cleanup complete")

if __name__ == "__main__":
    main()
