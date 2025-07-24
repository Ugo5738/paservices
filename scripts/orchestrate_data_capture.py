#!/usr/bin/env python3
"""
Orchestrates a multi-step, detachable data capture and analysis workflow.

This script manages the entire pipeline from property discovery to detailed analysis,
offering fine-grained control over which stages are executed.

Workflow Stages:
1.  **Search**: Triggers a background search for properties based on a location.
    - The `data_capture_rightmove_service` saves basic property data.
2.  **Scrape**: Fetches the URLs from the search results and triggers a
    detailed scrape for each, assigning a new unique `super_id` per property.
3.  **Orchestrate**: For each successfully scraped property, it calls an
    external analysis service (`api.supersami.com`), using the unique
    scrape `super_id` as the `phone_number` in the payload.

Usage Examples:
  # Run the full end-to-end workflow
  python scripts/orchestrate_data_capture.py --location "STATION^506" --api-token "YOUR_TOKEN" --mode full-flow

  # Run only the search part
  python scripts/orchestrate_data_capture.py --location "STATION^506" --api-token "YOUR_TOKEN" --mode search-only

  # Run search and then scrape only properties found in the last 24 hours
  python scripts/orchestrate_data_capture.py --location "STATION^506" --api-token "YOUR_TOKEN" --mode search-and-scrape --time-filter-hours 24
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

# --- Configuration ---
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
SUPER_ID_SERVICE_URL = os.getenv("SUPER_ID_SERVICE_URL", "http://localhost:8002")
DATA_CAPTURE_SERVICE_URL = os.getenv(
    "DATA_CAPTURE_SERVICE_URL", "http://localhost:8003"
)
EXTERNAL_ORCHESTRATION_URL = os.getenv(
    "ORCHESTRATION_API_URL",
    "https://api.supersami.com/api/orchestration/properties/analyze/",
)

M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")


# --- Helper Functions ---
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


# --- Core Workflow Functions ---


async def get_auth_token(client: httpx.AsyncClient) -> Optional[str]:
    """Step 1: Get an M2M authentication token."""
    print_color("▶️  Step 1: Authenticating with internal Auth Service...", "blue")
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
        print_color("✅ SUCCESS: Internal M2M token received.", "green")
        return token
    except Exception as e:
        print_color(f"❌ ERROR: Internal authentication failed. Details: {e}", "red")
        return None


async def get_super_id(
    client: httpx.AsyncClient, token: str, description: str
) -> Optional[str]:
    """Step 2: Get a Super ID for workflow tracking."""
    print_color(f"▶️  Requesting Super ID for: '{description}'...", "blue")
    url = f"{SUPER_ID_SERVICE_URL}/api/v1/super_ids"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"count": 1, "description": description}
    try:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        super_id = response.json().get("super_id")
        print_color(f"✅ SUCCESS: Super ID received: {super_id}", "green")
        return super_id
    except Exception as e:
        print_color(f"❌ ERROR: Could not get Super ID. Details: {e}", "red")
        return None


async def trigger_property_search(
    client: httpx.AsyncClient, token: str, super_id: str, location: str
) -> bool:
    """Triggers the property search background task."""
    print_color("\n▶️  Stage A: Triggering Property Search...", "magenta")
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/search/for-sale"
    headers = {"Authorization": f"Bearer {token}", "X-Super-ID": super_id}
    payload = {"location_identifier": location, "super_id": super_id}
    try:
        response = await client.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        print_color(f"✅ SUCCESS: Search request for '{location}' accepted.", "green")
        return True
    except Exception as e:
        print_color(f"❌ ERROR: Could not trigger property search. Details: {e}", "red")
        return False


async def get_properties_by_super_id(
    client: httpx.AsyncClient, token: str, search_super_id: str
) -> Optional[List[Dict[str, Any]]]:
    """Retrieves properties stored under a specific super_id."""
    print_color(
        f"\n▶️  Fetching search results for Super ID {search_super_id}...", "blue"
    )
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/by-super-id/{search_super_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = await client.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        properties = response.json().get("properties", [])
        print_color(
            f"✅ SUCCESS: Found {len(properties)} properties from the search.", "green"
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
        print_color(f"   - ❌ Scrape failed for {property_url}. Details: {e}", "red")
        return False


async def trigger_external_orchestration(
    client: httpx.AsyncClient, api_token: str, property_url: str, super_id_as_phone: str
) -> bool:
    """Calls the external orchestration service at api.supersami.com."""
    headers = {"Authorization": f"Bearer {api_token}"}
    payload = {
        "url": property_url,
        "phone_number": super_id_as_phone,  # Using super_id as phone_number
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
        print_color(
            f"   - ❌ External orchestration failed for {property_url}. Details: {e}",
            "red",
        )
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate data capture and analysis workflows."
    )
    parser.add_argument(
        "--location",
        required=True,
        help="Rightmove location identifier (e.g., 'STATION^506').",
    )
    parser.add_argument(
        "--api-token",
        required=True,
        help="Authentication token for the external api.supersami.com API.",
    )
    parser.add_argument(
        "--mode",
        choices=["search-only", "search-and-scrape", "full-flow"],
        default="full-flow",
        help="Workflow mode to execute.",
    )
    parser.add_argument(
        "--time-filter-hours",
        type=int,
        default=None,
        help="Only scrape properties found within the last N hours.",
    )
    parser.add_argument(
        "--wait-time",
        type=int,
        default=60,
        help="Seconds to wait for background search to complete.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the process without making live API calls.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="0-based index to start processing from.",
    )
    args = parser.parse_args()

    print_color(f"🚀 Starting Orchestration in '{args.mode}' mode 🚀", "yellow")
    if args.dry_run:
        print_color("DRY RUN MODE ENABLED", "yellow")

    async with httpx.AsyncClient() as client:
        # --- Stage 1: Search ---
        internal_token = await get_auth_token(client)
        if not internal_token:
            sys.exit(1)

        search_super_id = await get_super_id(
            client, internal_token, f"Search for location {args.location}"
        )
        if not search_super_id:
            sys.exit(1)

        if not args.dry_run:
            if not await trigger_property_search(
                client, internal_token, search_super_id, args.location
            ):
                sys.exit(1)
        else:
            print_color(
                f"[DRY RUN] Would trigger search for location '{args.location}' with super_id {search_super_id}",
                "yellow",
            )

        if args.mode == "search-only":
            print_color("\n🎉 Workflow complete (search-only mode). 🎉", "green")
            sys.exit(0)

        # --- Stage 2: Scrape ---
        print_color(
            f"\n▶️  Waiting {args.wait_time} seconds for search results...", "magenta"
        )
        if not args.dry_run:
            await asyncio.sleep(args.wait_time)

        properties = []
        if not args.dry_run:
            properties = await get_properties_by_super_id(
                client, internal_token, search_super_id
            )
            if properties is None:
                sys.exit(1)  # Indicates an error
        else:
            print_color("[DRY RUN] Would fetch properties from search.", "yellow")
            # Create dummy properties for dry run
            properties = [
                {
                    "property_url": f"/properties/12345678{i}",
                    "id": f"12345678{i}",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                for i in range(3)
            ]

        if not properties:
            print_color("No properties found from search. Halting workflow.", "yellow")
            sys.exit(0)

        # Time-based filtering
        if args.time_filter_hours is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(
                hours=args.time_filter_hours
            )
            print_color(
                f"Filtering properties created after {cutoff.isoformat()}", "magenta"
            )

            original_count = len(properties)
            properties = [
                p
                for p in properties
                if datetime.fromisoformat(p["created_at"]) > cutoff
            ]
            print_color(
                f"Filtered {original_count - len(properties)} properties based on timestamp. {len(properties)} remain.",
                "magenta",
            )

        print_color(
            f"\n▶️  Stage B: Starting Detailed Scrape for {len(properties)} properties...",
            "magenta",
        )

        successful_scrapes = []

        for i, prop in enumerate(properties):
            property_url = prop.get("property_url")
            prop_id = prop.get("id")
            if not property_url:
                print_color(
                    f"   - ⚠️ Skipping property {prop_id} due to missing URL.", "yellow"
                )
                continue

            full_url = f"https://www.rightmove.co.uk{property_url}"
            print_color(f"   ({i+1}/{len(properties)}) Processing: {full_url}", "blue")

            scrape_super_id = await get_super_id(
                client, internal_token, f"Detailed scrape for property ID {prop_id}"
            )
            if not scrape_super_id:
                print_color(
                    f"   - ❌ Could not get Super ID for {full_url}. Skipping.", "red"
                )
                continue

            if not args.dry_run:
                if await trigger_detailed_scrape(
                    client, internal_token, full_url, scrape_super_id
                ):
                    print_color(f"   - ✅ Scrape initiated.", "green")
                    successful_scrapes.append(
                        {"url": full_url, "super_id": scrape_super_id}
                    )
                await asyncio.sleep(2)  # Politeness delay
            else:
                print_color(
                    f"   - [DRY RUN] Would trigger scrape with super_id {scrape_super_id}",
                    "yellow",
                )
                successful_scrapes.append(
                    {"url": full_url, "super_id": scrape_super_id}
                )

        if args.mode == "search-and-scrape":
            print_color("\n🎉 Workflow complete (search-and-scrape mode). 🎉", "green")
            sys.exit(0)

        # --- Stage 3: External Orchestration ---
        print_color(
            f"\n▶️  Stage C: Triggering External Orchestration for {len(successful_scrapes)} properties...",
            "magenta",
        )
        orchestration_success_count = 0
        for i, scrape in enumerate(successful_scrapes):
            print_color(
                f"   ({i+1}/{len(successful_scrapes)}) Orchestrating for: {scrape['url']}",
                "blue",
            )
            if not args.dry_run:
                if await trigger_external_orchestration(
                    client, args.api_token, scrape["url"], scrape["super_id"]
                ):
                    print_color(f"   - ✅ External analysis triggered.", "green")
                    orchestration_success_count += 1
                await asyncio.sleep(2)  # Politeness delay
            else:
                print_color(
                    f"   - [DRY RUN] Would call external orchestrator, using super_id {scrape['super_id']} as phone_number.",
                    "yellow",
                )
                orchestration_success_count += 1

        print_color("\n🎉 Full Workflow Complete! 🎉", "green")
        print_color(
            f"   - Summary: Triggered external analysis for {orchestration_success_count}/{len(successful_scrapes)} successfully scraped properties.",
            "green",
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
        sys.exit(1)


# Mode 1: Search Only
# python scripts/orchestrate_data_capture.py \
#   --location "REGION^87490" \
#   --api-token "YOUR_EXTERNAL_API_TOKEN" \
#   --mode search-only
# This will trigger the search and then stop.
# toglle to be able do it once or do it repeated


# Mode 2: Search and Scrape (with time filter for daily runs)
# python scripts/orchestrate_data_capture.py \
#   --location "REGION^87490" \
#   --api-token "YOUR_EXTERNAL_API_TOKEN" \
#   --mode search-and-scrape \
#   --time-filter-hours 24
# This will search, then scrape only properties found in the last 24 hours, and then stop.
# separately do this once or repeated
# do it using date range not time frame, could include bedrooms, bathrooms
# the date range has to move with the repeating (to get fresh urls every new day)


# Mode 3: Full End-to-End Workflow
# python scripts/orchestrate_data_capture.py \
#   --location "STATION^506" \
#   --api-token "YOUR_EXTERNAL_API_TOKEN" \
#   --mode full-flow \
#   --wait-time 30
# This runs the entire process: searches, waits 30 seconds, scrapes all results, and then calls the external analysis service for each one.


# Dry Run (to test logic safely)
# python scripts/orchestrate_data_capture.py \
#   --location "STATION^506" \
#   --api-token "YOUR_EXTERNAL_API_TOKEN" \
#   --mode full-flow \
#   --dry-run
# This will print out the actions it would take at each step without making any live API calls.


# first principle's thinking is a super skill, the irony is it is super simple
# if you can't do 1 then don't do 100
# just in time
# lean manufacturing
