#!/usr/bin/env python3
"""
Finds recently scraped properties and triggers the external analysis workflow.

This script queries for properties that have been successfully scraped on a specific date,
then calls the external orchestration service (api.supersami.com) for each,
using the unique scrape `super_id` as the `phone_number` for user registration/association.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

# Shared utility functions
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
DATA_CAPTURE_SERVICE_URL = os.getenv(
    "DATA_CAPTURE_SERVICE_URL", "http://localhost:8003"
)
EXTERNAL_ORCHESTRATION_URL = os.getenv(
    "ORCHESTRATION_API_URL",
    "https://api.supersami.com/api/orchestration/properties/analyze/",
)
EXTERNAL_TOKEN_URL = "https://api.supersami.com/api/auth/authenticate-phone/"
M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")


def print_color(text, color):
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


async def get_internal_auth_token(client: httpx.AsyncClient) -> Optional[str]:
    print_color("▶️  Authenticating with INTERNAL Auth Service...", "blue")
    url = f"{AUTH_SERVICE_URL}/api/v1/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": M2M_CLIENT_ID,
        "client_secret": M2M_CLIENT_SECRET,
    }
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        print_color(f"❌ ERROR: Internal authentication failed. Details: {e}", "red")
        return None


async def get_external_api_token(
    client: httpx.AsyncClient, phone: str, password: str
) -> Optional[str]:
    print_color(
        "▶️  Step 1: Authenticating with EXTERNAL Orchestration Service...", "blue"
    )
    payload = {"phone_number": phone, "password": password}
    try:
        response = await client.post(EXTERNAL_TOKEN_URL, json=payload)
        response.raise_for_status()
        token = response.json().get("access")
        if not token:
            # Handle cases where the token key might be different, e.g., 'token'
            token = response.json().get("token")

        if not token:
            print_color("❌ ERROR: Token not found in external auth response.", "red")
            print(f"   Response JSON: {response.json()}")
            return None
        print_color("✅ SUCCESS: External API token received.", "green")
        return token
    except Exception as e:
        print_color(f"❌ ERROR: External authentication failed. Details: {e}", "red")
        # Add this line to print the response body on error, which is very helpful
        if hasattr(e, "response"):
            print(f"   Response Body: {e.response.text}")
        return None


async def get_properties_for_analysis(
    client: httpx.AsyncClient, token: str, args: argparse.Namespace
) -> Optional[List[Dict[str, Any]]]:
    """Retrieves properties from the database based on filter criteria."""
    print_color(
        "\n▶️  Step 2: Finding successfully SCRAPED properties to analyze...", "blue"
    )
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/scraped-listings"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "on_date": args.date,
        "from_time": args.from_time,
        "to_time": args.to_time,
        "min_bedrooms": args.min_bedrooms,
    }
    params = {k: v for k, v in params.items() if v is not None}

    try:
        response = await client.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        properties = response.json().get("properties", [])
        print_color(
            f"✅ SUCCESS: Found {len(properties)} properties ready for analysis.",
            "green",
        )
        return properties
    except Exception as e:
        print_color(f"❌ ERROR: Failed to retrieve properties. Details: {e}", "red")
        return None


async def trigger_external_orchestration(
    client: httpx.AsyncClient, api_token: str, property_url: str, super_id_as_phone: str
) -> bool:
    """Calls the external orchestration service."""
    headers = {"Authorization": f"Bearer {api_token}"}
    payload = {
        "url": property_url,
        "phone_number": super_id_as_phone,
        "source": "rightmove",
        "analysis_source": "batch_process",
    }
    try:
        response = await client.post(
            EXTERNAL_ORCHESTRATION_URL, json=payload, headers=headers, timeout=60
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print_color(f"   - ❌ Orchestration call failed. Details: {e}", "red")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Trigger external analysis for recently scraped properties."
    )
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parser.add_argument(
        "--api-phone",
        required=True,
        help="Phone number for the user account on api.supersami.com.",
    )
    parser.add_argument(
        "--api-password",
        required=True,
        help="Password for the user account on api.supersami.com.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=today_str,
        help="Analyze properties scraped on this date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--from-time", type=str, help="Optional start time on the given date (HH:MM)."
    )
    parser.add_argument(
        "--to-time", type=str, help="Optional end time on the given date (HH:MM)."
    )
    parser.add_argument(
        "--min-bedrooms", type=int, help="Minimum number of bedrooms to analyze."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without making external API calls.",
    )
    args = parser.parse_args()

    print_color("🚀 Starting External Analysis Trigger Workflow 🚀", "yellow")
    if args.dry_run:
        print_color("DRY RUN MODE ENABLED", "yellow")

    async with httpx.AsyncClient() as client:
        # Get both tokens up front
        external_api_token = await get_external_api_token(
            client, args.api_phone, args.api_password
        )
        internal_api_token = await get_internal_auth_token(client)

        if not external_api_token or not internal_api_token:
            sys.exit(1)

        properties = await get_properties_for_analysis(client, internal_api_token, args)
        if properties is None:
            sys.exit(1)
        if not properties:
            print_color("No properties to analyze. Exiting.", "yellow")
            sys.exit(0)

        print_color(
            f"\n▶️  Step 3: Starting external analysis trigger for {len(properties)} properties...",
            "magenta",
        )
        success_count = 0
        for i, prop in enumerate(properties):
            property_url = prop.get("property_url")
            super_id = prop.get("super_id")  # The unique ID from the scrape stage

            if not property_url or not super_id:
                print_color(
                    f"   - ⚠️ Skipping property {prop.get('id')} due to missing URL or Super ID.",
                    "yellow",
                )
                continue

            # This script doesn't need to construct the full URL if the API provides it
            # But we'll keep the logic just in case
            if not property_url.startswith("http"):
                full_url = f"https://www.rightmove.co.uk{property_url}"
            else:
                full_url = property_url

            print_color(
                f"   ({i+1}/{len(properties)}) Triggering for: {full_url}", "blue"
            )

            if not args.dry_run:
                if await trigger_external_orchestration(
                    client, external_api_token, full_url, super_id
                ):
                    print_color(
                        f"   - ✅ External analysis triggered using Super ID {super_id} as phone_number.",
                        "green",
                    )
                    success_count += 1
                await asyncio.sleep(2)
            else:
                print_color(
                    f"   - [DRY RUN] Would call external orchestrator for {full_url} with phone_number={super_id}",
                    "yellow",
                )
                success_count += 1

        print_color("\n🎉 External Analysis Trigger Workflow Complete! 🎉", "green")
        print_color(
            f"   - Summary: Triggered {success_count}/{len(properties)} analysis tasks.",
            "green",
        )


if __name__ == "__main__":
    asyncio.run(main())

# python scripts/trigger_analysis.py --api-phone "YOUR_SCRIPT_PHONE" --api-password "YOUR_SCRIPT_PASSWORD"
