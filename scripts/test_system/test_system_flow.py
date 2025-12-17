# /paservices/scripts/test_system_flow.py

import asyncio
import json
import os
import sys
from typing import Optional

import httpx

# --- Configuration ---
# Service URLs can be overridden via env vars; defaults target local docker-compose ports.
# AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
# SUPER_ID_SERVICE_URL = os.getenv("SUPER_ID_SERVICE_URL", "http://localhost:8002")
# DATA_CAPTURE_SERVICE_URL = os.getenv(
#     "DATA_CAPTURE_SERVICE_URL", "http://localhost:8003"
# )
AUTH_SERVICE_URL = "https://auth.supersami.com"
SUPER_ID_SERVICE_URL = "https://superid.supersami.com"
DATA_CAPTURE_SERVICE_URL = "https://data-capture-rightmove.supersami.com"

# Target property for the test
RIGHTMOVE_URL = os.getenv(
    "RIGHTMOVE_URL",
    "https://www.rightmove.co.uk/properties/154508327#/?channel=RES_LET",
)

# M2M client credentials. This script authenticates like the data-capture-rightmove service.
M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")


def build_url(base: str, path: str) -> str:
    base = (base or "").rstrip("/")
    path = (path or "").lstrip("/")
    return f"{base}/{path}"


# --- Helper Functions for Colored Output ---
def print_color(text, color):
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


# --- Test Flow Functions ---


async def get_auth_token() -> Optional[str]:
    """Step 1: Get an authentication token from the Auth Service."""
    print_color("▶️  Step 1: Authenticating with Auth Service...", "blue")
    # Some deployments mount under `/api/v1` while others expose routes at the root.
    candidate_paths = ("/api/v1/auth/token", "/auth/token")
    payload = {
        "grant_type": "client_credentials",
        "client_id": M2M_CLIENT_ID,
        "client_secret": M2M_CLIENT_SECRET,
    }
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            last_response: Optional[httpx.Response] = None
            for path in candidate_paths:
                url = build_url(AUTH_SERVICE_URL, path)
                response = await client.post(
                    url, json=payload, headers={"Content-Type": "application/json"}
                )
                last_response = response
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                token = response.json().get("access_token")
                if not token:
                    print_color(
                        "❌ ERROR: 'access_token' not found in auth response.", "red"
                    )
                    return None
                print_color(
                    f"✅  SUCCESS: Authentication successful. Token received from {url}.",
                    "green",
                )
                return token

            if last_response is not None:
                print_color(
                    f"❌ ERROR: Auth Service returned status {last_response.status_code}",
                    "red",
                )
                print(f"   URL tried: {last_response.request.url}")
                print(f"   Response: {last_response.text}")
            else:
                print_color("❌ ERROR: No auth URL candidates configured.", "red")
            return None
    except httpx.HTTPStatusError as e:
        print_color(
            f"❌ ERROR: Auth Service returned status {e.response.status_code}", "red"
        )
        print(f"   URL: {e.request.url}")
        print(f"   Response: {e.response.text}")
        return None
    except Exception as e:
        print_color(
            f"❌ ERROR: Could not connect to Auth Service at {AUTH_SERVICE_URL}.", "red"
        )
        print(f"   Details: {e}")
        return None


async def get_super_id(token: str) -> Optional[str]:
    """Step 2: Get a Super ID from the Super ID Service."""
    print_color("\n▶️  Step 2: Requesting Super ID from Super ID Service...", "blue")
    url = build_url(SUPER_ID_SERVICE_URL, "/api/v1/super_ids")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"count": 1}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            super_id_data = response.json()
            super_id = super_id_data.get("super_id")
            if not super_id:
                print_color(
                    "❌ ERROR: 'super_id' not found in service response.", "red"
                )
                return None
            print_color(f"✅  SUCCESS: Super ID received: {super_id}", "green")
            return super_id
    except httpx.HTTPStatusError as e:
        print_color(
            f"❌ ERROR: Super ID Service returned status {e.response.status_code}",
            "red",
        )
        print(f"   Response: {e.response.text}")
        if e.response.status_code == 403:
            print_color(
                "   HINT: This might mean the client doesn't have the 'super_id:generate' permission.",
                "yellow",
            )
        return None
    except Exception as e:
        print_color(f"❌ ERROR: Could not connect to Super ID Service at {url}.", "red")
        print(f"   Details: {e}")
        return None


async def capture_rightmove_data(token: str, super_id: str) -> bool:
    """Step 3: Trigger the Data Capture Rightmove Service."""
    print_color("\n▶️  Step 3: Triggering Data Capture Rightmove Service...", "blue")
    url = build_url(DATA_CAPTURE_SERVICE_URL, "/api/v1/properties/fetch/combined")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Super-ID": super_id,  # Include as a header for good practice
    }
    payload = {
        "property_url": RIGHTMOVE_URL,
        "super_id": super_id,  # The service expects this in the body
        "description": "System flow test via script",
    }
    try:
        async with httpx.AsyncClient(
            timeout=60, follow_redirects=True
        ) as client:  # Longer timeout for scraping
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()
            print_color(
                "✅  SUCCESS: Data Capture Service processed the request.", "green"
            )
            print("\n--- Final Response ---")
            print(json.dumps(response_data, indent=2))
            print("----------------------")
            return True
    except httpx.HTTPStatusError as e:
        print_color(
            f"❌ ERROR: Data Capture Service returned status {e.response.status_code}",
            "red",
        )
        print(f"   Response: {e.response.text}")
        return False
    except Exception as e:
        print_color(
            f"❌ ERROR: Could not connect to Data Capture Service at {url}.", "red"
        )
        print(f"   Details: {e}")
        return False


async def main():
    """Orchestrates the full system test flow."""
    print_color("🚀 Starting PA Services System Flow Test 🚀", "yellow")

    # Step 1
    token = await get_auth_token()
    if not token:
        print_color("\n🛑 Test failed at authentication step.", "red")
        sys.exit(1)

    # Step 2
    super_id = await get_super_id(token)
    print_color(f"\nSuper ID: {super_id}", "green")
    if not super_id:
        print_color("\n🛑 Test failed at Super ID generation step.", "red")
        sys.exit(1)

    # Step 3
    success = await capture_rightmove_data(token, super_id)
    if not success:
        print_color("\n🛑 Test failed at data capture step.", "red")
        sys.exit(1)

    print_color("\n🎉 System flow test completed successfully! 🎉", "green")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
        sys.exit(1)
