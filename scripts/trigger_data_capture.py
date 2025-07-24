#!/usr/bin/env python3
"""
Command-line script to trigger data capture workflows in the PA Services platform.

This script can be used to initiate two main types of data capture tasks:
1.  **Property Search**: Kicks off a background task to search for properties
    based on a location identifier and stores the results. This is analogous to
    the 'RapidAPI Search' functionality.
2.  **Detailed Scrape**: Fetches and stores comprehensive data for a single
    Rightmove property URL. This corresponds to the 'NEW RapidAPI detailed scrape'.

The script follows the standard system workflow:
- Authenticates with the Auth Service to get a machine-to-machine (M2M) token.
- Obtains a unique 'super_id' from the Super ID Service to trace the workflow.
- Calls the appropriate endpoint on the Data Capture Rightmove Service.

Usage:
  - To trigger a search:
    python scripts/trigger_data_capture.py search --location "STATION^506"

  - To trigger a detailed scrape:
    python scripts/trigger_data_capture.py scrape --url "https://www.rightmove.co.uk/properties/123456789"
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Optional

import httpx

# --- Configuration ---
# Service URLs are loaded from environment variables, with sensible defaults for local dev.
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
SUPER_ID_SERVICE_URL = os.getenv("SUPER_ID_SERVICE_URL", "http://localhost:8002")
DATA_CAPTURE_SERVICE_URL = os.getenv(
    "DATA_CAPTURE_SERVICE_URL", "http://localhost:8003"
)

# M2M client credentials for this script to authenticate with the Auth Service.
# These should match the credentials of a registered app_client in the auth_service database.
# For local development, these are typically stored in a .env file.
M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")


# --- Helper Functions for Colored Output ---
def print_color(text, color):
    """Prints text in a given color for better readability in the terminal."""
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


# --- Core Workflow Functions ---


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
        response = await client.post(url, json=payload)
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            print_color("❌ ERROR: 'access_token' not found in auth response.", "red")
            return None
        print_color("✅ SUCCESS: Authentication successful. Token received.", "green")
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


async def get_super_id(client: httpx.AsyncClient, token: str) -> Optional[str]:
    """Step 2: Get a Super ID from the Super ID Service."""
    print_color("\n▶️  Step 2: Requesting Super ID from Super ID Service...", "blue")
    url = f"{SUPER_ID_SERVICE_URL}/api/v1/super_ids"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"count": 1}
    try:
        response = await client.post(url, headers=headers, json=payload)
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
        print_color(f"❌ ERROR: Could not connect to Super ID Service at {url}.", "red")
        print(f"   Details: {e}")
        return None


# --- Main Task Functions ---


async def trigger_property_search(
    client: httpx.AsyncClient, token: str, super_id: str, location: str
):
    """Triggers the property search background task."""
    print_color("\n▶️  Step 3: Triggering Property Search...", "blue")
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/search/for-sale"
    headers = {"Authorization": f"Bearer {token}", "X-Super-ID": super_id}
    payload = {
        "location_identifier": location,
        "super_id": super_id,
        "description": f"Triggered search for location: {location}",
    }
    try:
        response = await client.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        print_color(
            "✅ SUCCESS: Search request accepted. Processing will happen in the background.",
            "green",
        )
        print("\n--- Response from Data Capture Service ---")
        print(json.dumps(response.json(), indent=2))
        print("------------------------------------------")
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


async def trigger_detailed_scrape(
    client: httpx.AsyncClient, token: str, super_id: str, property_url: str
):
    """Triggers the detailed property scrape task."""
    print_color("\n▶️  Step 3: Triggering Detailed Property Scrape...", "blue")
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/fetch/combined"
    headers = {"Authorization": f"Bearer {token}", "X-Super-ID": super_id}
    payload = {
        "property_url": property_url,
        "super_id": super_id,
        "description": f"Detailed scrape for URL: {property_url}",
    }
    try:
        # This can be a long-running operation, so we use a longer timeout.
        response = await client.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        print_color("✅ SUCCESS: Detailed scrape request completed.", "green")
        print("\n--- Response from Data Capture Service ---")
        print(json.dumps(response.json(), indent=2))
        print("------------------------------------------")
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


# --- Main Execution Block ---


async def main():
    """Main function to parse arguments and orchestrate the workflow."""
    parser = argparse.ArgumentParser(
        description="Trigger data capture workflows for PA Services."
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # Sub-parser for the 'search' command
    search_parser = subparsers.add_parser(
        "search", help="Trigger a property search by location."
    )
    search_parser.add_argument(
        "--location",
        required=True,
        help="Rightmove location identifier (e.g., 'STATION^506').",
    )

    # Sub-parser for the 'scrape' command
    scrape_parser = subparsers.add_parser(
        "scrape", help="Trigger a detailed scrape of a single property URL."
    )
    scrape_parser.add_argument(
        "--url", required=True, help="Full Rightmove property URL."
    )

    args = parser.parse_args()

    print_color("🚀 Starting PA Services Data Capture Workflow 🚀", "yellow")

    async with httpx.AsyncClient() as client:
        # Step 1: Authentication
        token = await get_auth_token(client)
        if not token:
            print_color("\n🛑 Workflow failed at authentication step.", "red")
            sys.exit(1)

        # Step 2: Super ID Generation
        super_id = await get_super_id(client, token)
        if not super_id:
            print_color("\n🛑 Workflow failed at Super ID generation step.", "red")
            sys.exit(1)

        # Step 3: Execute the chosen command
        success = False
        if args.command == "search":
            success = await trigger_property_search(
                client, token, super_id, args.location
            )
        elif args.command == "scrape":
            success = await trigger_detailed_scrape(client, token, super_id, args.url)

        if success:
            print_color("\n🎉 Workflow completed successfully! 🎉", "green")
        else:
            print_color("\n🛑 Workflow failed at data capture step.", "red")
            sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
        sys.exit(1)
