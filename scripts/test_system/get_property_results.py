#!/usr/bin/env python3
"""
Retrieves granular property data for a specific Property ID.
Usage: python scripts/test_system/get_property_results.py --property-id <ID>
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Optional

import httpx

# Configuration (defaults match docker-compose)
AUTH_SERVICE_URL = "https://auth.supersami.com"
SUPER_ID_SERVICE_URL = "https://superid.supersami.com"
DATA_CAPTURE_SERVICE_URL = "https://data-capture-rightmove.supersami.com"

# M2M Credentials (defaults for dev)
M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")


def print_color(text, color):
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


async def get_auth_token() -> Optional[str]:
    print_color("▶️  Authenticating...", "blue")
    url = f"{AUTH_SERVICE_URL}/api/v1/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": M2M_CLIENT_ID,
        "client_secret": M2M_CLIENT_SECRET,
    }
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json().get("access_token")
    except Exception as e:
        print_color(f"❌ Auth failed: {e}", "red")
        return None


async def fetch_and_save(
    client: httpx.AsyncClient, token: str, endpoint: str, filename: str
):
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}
    print_color(f"▶️  Fetching {endpoint}...", "blue")
    try:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 404:
            print_color(f"⚠️  Data not found at {endpoint} (yet?)", "red")
            return
        resp.raise_for_status()
        data = resp.json()

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print_color(f"✅ Saved to {filename}", "green")
    except Exception as e:
        print_color(f"❌ Failed to fetch {endpoint}: {e}", "red")


async def main():
    parser = argparse.ArgumentParser(description="Get property analysis results.")
    parser.add_argument(
        "--property-id", required=True, help="The Rightmove Property ID"
    )
    args = parser.parse_args()

    token = await get_auth_token()
    if not token:
        sys.exit(1)

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Fetch General Details
        await fetch_and_save(
            client,
            token,
            f"details/{args.property_id}",
            f"property_details_{args.property_id}.json",
        )

        # 2. Fetch For-Sale Specifics
        await fetch_and_save(
            client,
            token,
            f"property-for-sale/{args.property_id}",
            f"property_for_sale_{args.property_id}.json",
        )

    print_color("\nDone!", "green")


if __name__ == "__main__":
    asyncio.run(main())
