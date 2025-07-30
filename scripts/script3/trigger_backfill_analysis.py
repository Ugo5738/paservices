# /paservices/scripts/trigger_backfill_analysis.py
import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

# --- Configuration ---
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
DATA_CAPTURE_RIGHTMOVE_SERVICE_URL = os.getenv(
    "DATA_CAPTURE_RIGHTMOVE_SERVICE_URL", "http://localhost:8003"
)
M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")

EXTERNAL_TOKEN_URL = "https://api.supersami.com/api/auth/authenticate-phone/"
EXTERNAL_ORCHESTRATION_URL = (
    "https://api.supersami.com/api/orchestration/properties/analyze/"
)


# --- Helper Function for Colored Output ---
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


# --- Service Interaction Functions ---
async def get_internal_auth_token(client: httpx.AsyncClient) -> Optional[str]:
    print_color("▶ Authenticating with internal Auth Service...", "blue")
    url = f"{AUTH_SERVICE_URL}/api/v1/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": M2M_CLIENT_ID,
        "client_secret": M2M_CLIENT_SECRET,
    }
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        print_color("✅ Internal authentication successful.", "green")
        return response.json().get("access_token")
    except Exception as e:
        print_color(f"❌ ERROR: Internal authentication failed. Details: {e}", "red")
        return None


async def get_external_api_token(
    client: httpx.AsyncClient, phone: str, password: str
) -> Optional[str]:
    print_color("▶ Authenticating with EXTERNAL Orchestration Service...", "blue")
    payload = {"phone_number": phone, "password": password}
    try:
        response = await client.post(EXTERNAL_TOKEN_URL, json=payload)
        response.raise_for_status()
        token = response.json().get("access")
        if not token:
            print_color(
                "  - ❌ ERROR: 'access' token not found in external auth response.",
                "red",
            )
            return None
        print_color("✅ External API token received.", "green")
        return token
    except Exception as e:
        print_color(f"❌ ERROR: External authentication failed. Details: {e}", "red")
        return None


async def fetch_scraped_data_and_build_map(
    client: httpx.AsyncClient, token: str, days_to_check: int = 5
) -> Dict[str, str]:
    print_color(
        f"▶ Fetching scraped properties from the last {days_to_check} days...", "blue"
    )
    url = f"{DATA_CAPTURE_RIGHTMOVE_SERVICE_URL}/api/v1/properties/scraped-listings"
    headers = {"Authorization": f"Bearer {token}"}
    all_properties = []

    for i in range(days_to_check):
        check_date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime(
            "%Y-%m-%d"
        )
        params = {"on_date": check_date, "limit": 5000}
        print_color(f"  - Querying for date: {check_date}...", "blue")
        try:
            response = await client.get(
                url, headers=headers, params=params, timeout=120
            )
            response.raise_for_status()
            properties = response.json().get("properties", [])
            if properties:
                all_properties.extend(properties)
                print_color(f"  - Found {len(properties)} properties.", "green")
        except Exception as e:
            print_color(
                f"  - ⚠️ Could not fetch data for {check_date}. Details: {e}", "yellow"
            )

    # --- FIX: INTELLIGENT URL NORMALIZATION ---
    url_map = {}
    for prop in all_properties:
        if prop.get("property_url"):
            # Start with the relative path
            relative_url = prop["property_url"]
            # If it's a full (and likely duplicated) URL, strip the domain
            if "http" in relative_url:
                relative_url = "/" + "/".join(relative_url.split("/")[3:])

            # Construct the clean, final URL and strip any fragments
            clean_url = f"https://www.rightmove.co.uk{relative_url}".split("#")[0]
            url_map[clean_url] = prop["super_id"]

    print_color(f"✅ Built lookup map with {len(url_map)} unique, clean URLs.", "green")
    return url_map


async def trigger_external_orchestration(
    client: httpx.AsyncClient, api_token: str, property_url: str, super_id_as_phone: str
):
    print_color(
        f"  - Triggering external analysis for super_id: {super_id_as_phone}...", "blue"
    )
    headers = {"Authorization": f"Bearer {api_token}"}
    payload = {
        "url": property_url,
        "phone_number": super_id_as_phone,
        "source": "rightmove",
        "analysis_source": "batch_process_backfill",
    }
    try:
        response = await client.post(
            EXTERNAL_ORCHESTRATION_URL, json=payload, headers=headers, timeout=60
        )
        response.raise_for_status()
        print_color(f"  - ✅ External analysis triggered successfully.", "green")
        return True
    except Exception as e:
        print_color(f"  - ❌ External orchestration failed. Details: {e}", "red")
        return False


async def main(csv_path: str, start_index: int, api_phone: str, api_password: str):
    print_color(
        "🚀 Starting External Analysis Trigger Workflow for Backfill 🚀", "yellow"
    )

    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Normalize the CSV URLs on read
            target_urls = {row["full_url"].split("#")[0] for row in reader}
    except FileNotFoundError:
        print_color(f"❌ ERROR: The file '{csv_path}' was not found.", "red")
        return
    except KeyError:
        print_color("❌ ERROR: CSV must have a header column named 'full_url'.", "red")
        return

    async with httpx.AsyncClient() as client:
        internal_token = await get_internal_auth_token(client)
        if not internal_token:
            return

        external_token = await get_external_api_token(client, api_phone, api_password)
        if not external_token:
            return

        url_to_super_id_map = await fetch_scraped_data_and_build_map(
            client, internal_token
        )
        if not url_to_super_id_map:
            print_color("Could not fetch scrape data. Aborting.", "red")
            return

        urls_to_process = sorted(
            [url for url in target_urls if url in url_to_super_id_map]
        )

        if not urls_to_process:
            print_color(
                "Could not find a match between the CSV and any recently scraped properties. Aborting.",
                "red",
            )
            return

        if start_index >= len(urls_to_process):
            print_color(
                f"Start index ({start_index}) is beyond the end of the list. Nothing to process.",
                "yellow",
            )
            return

        final_urls_to_process = urls_to_process[start_index:]

        print_color(f"Found {len(target_urls)} total unique URLs in CSV.", "magenta")
        print_color(
            f"Found {len(url_to_super_id_map)} successfully scraped properties in the lookup map.",
            "magenta",
        )
        print_color(
            f"Found {len(urls_to_process)} matching properties to process.", "magenta"
        )
        print_color(
            f"Starting from index {start_index}. Processing {len(final_urls_to_process)} properties.",
            "magenta",
        )

        for i, url in enumerate(final_urls_to_process, start=start_index + 1):
            print_color(
                f"\n--- Processing Item {i}/{len(urls_to_process)}: {url} ---", "yellow"
            )

            super_id_to_use = url_to_super_id_map.get(url)

            if not super_id_to_use:
                print_color(
                    f"  - ⚠️ SKIPPED: Could not find a matching super_id (this should not happen).",
                    "yellow",
                )
                continue

            await trigger_external_orchestration(
                client, external_token, url, super_id_to_use
            )
            await asyncio.sleep(2)

    print_color("\n🎉 External analysis trigger process complete! 🎉", "green")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Trigger external analysis for a list of scraped properties."
    )
    parser.add_argument(
        "csv_path", help="Path to the original CSV file of property URLs."
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="0-based index to start processing from.",
    )
    parser.add_argument(
        "--api-phone",
        required=True,
        help="Phone number for the external orchestration service.",
    )
    parser.add_argument(
        "--api-password",
        required=True,
        help="Password for the external orchestration service.",
    )
    args = parser.parse_args()

    asyncio.run(
        main(args.csv_path, args.start_index, args.api_phone, args.api_password)
    )


# -- The DISTINCT keyword ensures that each unique URL is returned only once.
# SELECT DISTINCT
#   'https://www.rightmove.co.uk' || property_url AS full_url
# FROM
#   rightmove.property_listings
# WHERE
#   id IN (
#     -- This subquery correctly identifies the UNIQUE missing property IDs
#     SELECT id FROM rightmove.property_listings WHERE DATE(created_at) = '2025-07-24'
#     EXCEPT
#     SELECT id FROM rightmove.api_properties_details_v2 WHERE DATE(created_at) = '2025-07-26'
#   )
#   -- Ensure we only get URLs for properties discovered on the correct date
#   AND DATE(created_at) = '2025-07-24';
