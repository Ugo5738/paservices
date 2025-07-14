# /paservices/scripts/test_system_flow.py

import asyncio
import json
import os
import sys
import uuid
from typing import Dict, Optional, Tuple

import httpx

# --- Configuration ---
# These URLs correspond to the ports mapped in your root docker-compose.yml
AUTH_SERVICE_URL = "http://localhost:8001"
SUPER_ID_SERVICE_URL = "http://localhost:8002"
DATA_CAPTURE_SERVICE_URL = "http://localhost:8003"

# Target property for the test
RIGHTMOVE_URL = "https://www.rightmove.co.uk/properties/154508327#/?channel=RES_LET"

# M2M client credentials from data_capture_rightmove_service/.env.dev
# This script authenticates as if it were the data-capture-rightmove-service
CLIENT_ID = "fe2c7655-0860-4d98-9034-cd5e1ac90a41"
CLIENT_SECRET = "dev-rightmove-service-secret"


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
    url = f"{AUTH_SERVICE_URL}/api/v1/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url, json=payload, headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            token_data = response.json()
            token = token_data.get("access_token")
            if not token:
                print_color(
                    "❌ ERROR: 'access_token' not found in auth response.", "red"
                )
                return None
            print_color(
                "✅  SUCCESS: Authentication successful. Token received.", "green"
            )
            return token
    except httpx.HTTPStatusError as e:
        print_color(
            f"❌ ERROR: Auth Service returned status {e.response.status_code}", "red"
        )
        print(f"   Response: {e.response.text}")
        return None
    except Exception as e:
        print_color(f"❌ ERROR: Could not connect to Auth Service at {url}.", "red")
        print(f"   Details: {e}")
        return None


async def get_super_id(token: str) -> Optional[str]:
    """Step 2: Get a Super ID from the Super ID Service."""
    print_color("\n▶️  Step 2: Requesting Super ID from Super ID Service...", "blue")
    url = f"{SUPER_ID_SERVICE_URL}/api/v1/super_ids"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"count": 1}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
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
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/fetch/combined"
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
            timeout=60
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
