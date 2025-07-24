#!/usr/bin/env python3
"""
Finds recently discovered properties and triggers a detailed scrape for each.

This script queries the database for properties found on a specific date
(and other optional criteria), then for each property, it gets a new unique super_id
and calls the detailed scrape endpoint.
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

# Shared utility functions
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
SUPER_ID_SERVICE_URL = os.getenv("SUPER_ID_SERVICE_URL", "http://localhost:8002")
DATA_CAPTURE_SERVICE_URL = os.getenv(
    "DATA_CAPTURE_SERVICE_URL", "http://localhost:8003"
)
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


async def get_super_id(
    client: httpx.AsyncClient, token: str, description: str
) -> Optional[str]:
    url = f"{SUPER_ID_SERVICE_URL}/api/v1/super_ids"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"count": 1, "description": description}
    try:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("super_id")
    except Exception:
        return None


async def get_properties_to_scrape(
    client: httpx.AsyncClient, token: str, args: argparse.Namespace
) -> Optional[List[Dict[str, Any]]]:
    """Retrieves properties from the database based on filter criteria."""
    print_color("\n▶️  Step 1: Finding properties to scrape...", "blue")
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/listings"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "on_date": args.date,
        "from_time": args.from_time,
        "to_time": args.to_time,
        "min_bedrooms": args.min_bedrooms,
        "max_bedrooms": args.max_bedrooms,
        "min_bathrooms": args.min_bathrooms,
        "max_bathrooms": args.max_bathrooms,
    }
    params = {k: v for k, v in params.items() if v is not None}

    try:
        response = await client.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        properties = response.json().get("properties", [])
        print_color(
            f"✅ SUCCESS: Found {len(properties)} properties matching criteria.",
            "green",
        )
        return properties
    except Exception as e:
        print_color(f"❌ ERROR: Failed to retrieve properties. Details: {e}", "red")
        return None


async def trigger_detailed_scrape(
    client: httpx.AsyncClient, token: str, property_url: str, scrape_super_id: str
) -> bool:
    """Triggers the detailed property scrape task."""
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/fetch/combined"
    headers = {"Authorization": f"Bearer {token}", "X-Super-ID": scrape_super_id}
    payload = {"property_url": property_url, "super_id": scrape_super_id}
    try:
        response = await client.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return True
    except Exception as e:
        print_color(f"   - ❌ Scrape failed. Details: {e}", "red")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Trigger detailed scrapes for recently found properties."
    )
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parser.add_argument(
        "--date",
        type=str,
        default=today_str,
        help="Scrape properties found on this date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--from-time", type=str, help="Optional start time on the given date (HH:MM)."
    )
    parser.add_argument(
        "--to-time", type=str, help="Optional end time on the given date (HH:MM)."
    )
    parser.add_argument(
        "--min-bedrooms", type=int, help="Minimum number of bedrooms to scrape."
    )
    parser.add_argument(
        "--max-bedrooms", type=int, help="Maximum number of bedrooms to scrape."
    )
    parser.add_argument(
        "--min-bathrooms", type=int, help="Minimum number of bathrooms to scrape."
    )
    parser.add_argument(
        "--max-bathrooms", type=int, help="Maximum number of bathrooms to scrape."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without making scrape calls."
    )
    args = parser.parse_args()

    print_color("🚀 Starting Detailed Scrape Workflow 🚀", "yellow")
    if args.dry_run:
        print_color("DRY RUN MODE ENABLED", "yellow")

    async with httpx.AsyncClient() as client:
        internal_token = await get_internal_auth_token(client)
        if not internal_token:
            sys.exit(1)

        properties = await get_properties_to_scrape(client, internal_token, args)
        if properties is None:
            sys.exit(1)
        if not properties:
            print_color("No properties to scrape. Exiting.", "yellow")
            sys.exit(0)

        print_color(
            f"\n▶️  Step 2: Starting detailed scrape for {len(properties)} properties...",
            "magenta",
        )
        success_count = 0
        for i, prop in enumerate(properties):
            property_url = prop.get("property_url")

            prop_id = prop.get("id")
            if not property_url:
                print_color(
                    f"   - ⚠️ Skipping property {prop_id} due to missing URL.", "yellow"
                )
                continue

            full_url = f"https://www.rightmove.co.uk{property_url}"
            print_color(f"   ({i+1}/{len(properties)}) Scraping: {full_url}", "blue")

            scrape_super_id = await get_super_id(
                client, internal_token, f"Detailed scrape for property ID {prop_id}"
            )
            if not scrape_super_id:
                print_color(f"   - ❌ Could not get Super ID. Skipping.", "red")
                continue

            if not args.dry_run:
                if await trigger_detailed_scrape(
                    client, internal_token, full_url, scrape_super_id
                ):
                    print_color(
                        f"   - ✅ Scrape initiated with Super ID: {scrape_super_id}",
                        "green",
                    )
                    success_count += 1
                await asyncio.sleep(2)  # Politeness delay
            else:
                print_color(
                    f"   - [DRY RUN] Would trigger scrape with Super ID: {scrape_super_id}",
                    "yellow",
                )
                success_count += 1

        print_color("\n🎉 Detailed Scrape Workflow Complete! 🎉", "green")
        print_color(
            f"   - Summary: Initiated {success_count}/{len(properties)} detailed scrapes.",
            "green",
        )


if __name__ == "__main__":
    asyncio.run(main())

# The --date will default to today's date
# python scripts/scrape_details.py

# python scripts/scrape_details.py --date "2025-10-26" --from-time "09:00" --to-time "17:00" --min-bedrooms 3 --max-bedrooms 3
