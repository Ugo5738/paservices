#!/usr/bin/env python3
"""
End-to-end test script for the Floorplan Analysis Service workflow.

This script simulates a client's request to start a floorplan analysis by:
1. Authenticating with the Auth Service to get a machine-to-machine (M2M) token.
2. Requesting a unique `super_id` from the Super ID Service to track the entire workflow.
3. Calling the Floorplan Service's `/analyze` endpoint with the `super_id`, a property ID,
   and a list of floorplan URLs.

This verifies the successful initiation of an analysis task and confirms the integration
between the core services.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

import httpx

# --- Configuration ---
# Service URLs are loaded from environment variables with defaults for local development
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
SUPER_ID_SERVICE_URL = os.getenv("SUPER_ID_SERVICE_URL", "http://localhost:8002")
FLOORPLAN_SERVICE_URL = os.getenv(
    "FLOORPLAN_SERVICE_URL", "http://localhost:8004"
)  # Assuming port 8004 for local dev

# M2M client credentials (should match the client created for this purpose)
M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")


# --- Helper Function for Colored Output ---
def print_color(text, color):
    """Prints text in a specified color for better readability."""
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


def setup_arg_parser() -> argparse.ArgumentParser:
    """Sets up the argument parser for the script."""
    parser = argparse.ArgumentParser(
        description="Trigger a floorplan analysis workflow with one or more image URLs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--property-id",
        required=True,
        help="A unique identifier for the property (e.g., 'rightmove-12345').",
    )
    parser.add_argument(
        "--floorplan-urls",
        required=True,
        nargs="+",  # Allows one or more URLs to be passed
        help="One or more full URLs to the floorplan images.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the workflow and print the final payload without sending it.",
    )
    return parser


async def get_auth_token(client: httpx.AsyncClient) -> Optional[str]:
    """Step 1: Get an authentication token from the Auth Service."""
    print_color("▶️  Step 1: Authenticating with Auth Service...", "blue")
    url = f"{AUTH_SERVICE_URL}/api/v1/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": M2M_CLIENT_ID,
        "client_secret": M2M_CLIENT_SECRET,
    }
    try:
        response = await client.post(url, json=payload, timeout=10)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            print_color("❌ ERROR: 'access_token' not found in auth response.", "red")
            return None
        print_color("✅ SUCCESS: Authentication successful.", "green")
        return token
    except httpx.HTTPStatusError as e:
        print_color(
            f"❌ ERROR: Auth Service returned status {e.response.status_code}", "red"
        )
        print(f"   Response: {e.response.text}")
        return None
    except Exception as e:
        print_color(
            f"❌ ERROR: Could not connect to Auth Service at {url}. Is it running?",
            "red",
        )
        print(f"   Details: {e}")
        return None


async def get_super_id(
    client: httpx.AsyncClient, token: str, description: str
) -> Optional[str]:
    """Step 2: Get a Super ID from the Super ID Service."""
    print_color(
        f"▶️  Step 2: Requesting Super ID for workflow: '{description}'...", "blue"
    )
    url = f"{SUPER_ID_SERVICE_URL}/api/v1/super_ids"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"count": 1, "metadata": {"description": description}}
    try:
        response = await client.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        super_id = response.json().get("super_id")
        if not super_id:
            print_color("❌ ERROR: 'super_id' not found in service response.", "red")
            return None
        print_color(f"✅ SUCCESS: Super ID received: {super_id}", "green")
        return super_id
    except httpx.HTTPStatusError as e:
        print_color(
            f"❌ ERROR: Super ID Service returned status {e.response.status_code}",
            "red",
        )
        print(f"   Response: {e.response.text}")
        return None
    except Exception as e:
        print_color(
            f"❌ ERROR: Could not connect to Super ID Service at {url}. Is it running?",
            "red",
        )
        print(f"   Details: {e}")
        return None


async def trigger_floorplan_analysis(
    client: httpx.AsyncClient,
    token: str,
    super_id: str,
    property_id: str,
    urls: List[str],
) -> bool:
    """Step 3: Trigger the Floorplan Analysis Service."""
    print_color("\n▶️  Step 3: Triggering Floorplan Analysis Service...", "magenta")
    url = f"{FLOORPLAN_SERVICE_URL}/api/v1/floorplans/analyze"
    headers = {"Authorization": f"Bearer {token}"}

    # Construct the floorplans dictionary from the list of URLs
    floorplans_payload = {}
    for i, image_url in enumerate(urls):
        client_key = f"fp{i+1}"  # e.g., "fp1", "fp2"
        floorplans_payload[client_key] = {
            "url": image_url,
            "notes": f"Test floorplan {i+1} for property {property_id}",
        }

    payload = {
        "super_id": super_id,
        "property_id": property_id,
        "floorplans": floorplans_payload,
    }

    print("   - Payload to be sent:")
    print(json.dumps(payload, indent=2))

    try:
        response = await client.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        print_color("✅ SUCCESS: Floorplan analysis request accepted.", "green")
        print(f"   - Response: {response.text}")
        return True
    except httpx.HTTPStatusError as e:
        print_color(
            f"❌ ERROR: Floorplan Service returned status {e.response.status_code}",
            "red",
        )
        print(f"   Response: {e.response.text}")
        return False
    except Exception as e:
        print_color(
            f"❌ ERROR: Could not connect to Floorplan Service at {url}. Is it running?",
            "red",
        )
        print(f"   Details: {e}")
        return False


async def main():
    """Orchestrates the full system test flow."""
    parser = setup_arg_parser()
    args = parser.parse_args()

    print_color("🚀 Starting Floorplan Analysis System Flow Test 🚀", "yellow")

    async with httpx.AsyncClient() as client:
        # Step 1: Authentication
        token = await get_auth_token(client)
        if not token:
            print_color("\n🛑 Test failed at authentication step.", "red")
            sys.exit(1)

        # Step 2: Super ID Generation
        super_id = await get_super_id(
            client, token, f"Floorplan analysis for property {args.property_id}"
        )
        if not super_id:
            print_color("\n🛑 Test failed at Super ID generation step.", "red")
            sys.exit(1)

        # Step 3: Trigger Analysis
        if args.dry_run:
            print_color(
                "\n[DRY RUN] Skipping actual call to Floorplan Service.", "yellow"
            )
            success = True
        else:
            success = await trigger_floorplan_analysis(
                client, token, super_id, args.property_id, args.floorplan_urls
            )

        if not success:
            print_color("\n🛑 Test failed at floorplan analysis trigger step.", "red")
            sys.exit(1)

    print_color("\n🎉 System flow test completed successfully! 🎉", "green")


if __name__ == "__main__":
    # Example Usage:
    # python scripts/test_system/test_floorplan_analysis.py --property-id "rightmove-abc123" --floorplan-urls "https://example.com/fp1.png" "https://example.com/fp2.png"
    #
    # To run a dry run:
    # python scripts/test_system/test_floorplan_analysis.py --property-id "rightmove-abc123" --floorplan-urls "https://example.com/fp1.png" --dry-run
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
        sys.exit(1)
