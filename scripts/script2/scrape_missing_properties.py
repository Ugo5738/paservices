# /paservices/scripts/scrape_missing_properties.py
import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
from jose import jwt

# --- Configuration ---
# NOTE: When running locally, ensure your services are mapped to these localhost ports in your root docker-compose.yml
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
SUPER_ID_SERVICE_URL = os.getenv("SUPER_ID_SERVICE_URL", "http://localhost:8002")
DATA_CAPTURE_RIGHTMOVE_SERVICE_URL = os.getenv(
    "DATA_CAPTURE_RIGHTMOVE_SERVICE_URL", "http://localhost:8003"
)

M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")
# This secret key MUST match the one used by your auth_service to sign the tokens.
M2M_JWT_SECRET_KEY = os.getenv(
    "M2M_JWT_SECRET_KEY",
    "a8148b76fb99c3bf898d8ad97b4a0eb978a29db3ad683c0544170a6e43b3968d",
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
async def get_auth_token(client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    print_color("  - Authenticating with Auth Service...", "blue")
    url = f"{AUTH_SERVICE_URL}/api/v1/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": M2M_CLIENT_ID,
        "client_secret": M2M_CLIENT_SECRET,
    }
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")

        # --- FIX: CORRECTLY DECODE THE TOKEN ---
        # The 'key' argument is required to decode the token's payload.
        payload = jwt.decode(
            access_token,
            key=M2M_JWT_SECRET_KEY,  # <-- This was the missing argument causing the bug
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        print_color(
            f"  - ✅ New token acquired. Valid until: {expires_at.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "green",
        )
        return {"token": access_token, "expires_at": expires_at}
    except Exception as e:
        print_color(f"  - ❌ Error getting auth token: {e}", "red")
        return None


async def get_super_id(
    client: httpx.AsyncClient, token: str, description: str
) -> Optional[str]:
    print_color("  - Requesting new Super ID for this scrape task...", "blue")
    url = f"{SUPER_ID_SERVICE_URL}/api/v1/super_ids"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"count": 1, "description": description}
    try:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        super_id = response.json().get("super_id")
        print_color(f"  - ✅ Super ID received: {super_id}", "green")
        return super_id
    except Exception as e:
        print_color(f"  - ❌ Error getting super_id: {e}", "red")
        return None


async def trigger_detailed_scrape(
    client: httpx.AsyncClient, property_url: str, scrape_super_id: str
):
    print_color(f"  - Triggering detailed scrape for {property_url}...", "blue")
    url = f"{DATA_CAPTURE_RIGHTMOVE_SERVICE_URL}/api/v1/properties/fetch/combined"
    headers = {"X-Super-ID": scrape_super_id}
    payload = {"property_url": property_url, "super_id": scrape_super_id}
    try:
        response = await client.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        print_color(f"  - ✅ Scrape initiated successfully.", "green")
        return True
    except Exception as e:
        print_color(
            f"  - ❌ FAILED to initiate scrape for {property_url}. Details: {e}", "red"
        )
        return False


async def main(file_path: str, start_index: int):
    print_color("🚀 Starting Backfill Scrape Workflow 🚀", "yellow")
    try:
        with open(file_path, mode="r", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            all_urls = [row["full_url"] for row in reader]
    except FileNotFoundError:
        print_color(f"❌ ERROR: The file '{file_path}' was not found.", "red")
        return
    except KeyError:
        print_color(f"❌ ERROR: CSV must have a header column named 'full_url'.", "red")
        return

    if start_index >= len(all_urls):
        print_color(
            f"Start index ({start_index}) is beyond the end of the file. Nothing to process.",
            "yellow",
        )
        return

    urls_to_process = all_urls[start_index:]

    print_color(f"Found {len(all_urls)} total properties.", "magenta")
    print_color(
        f"Starting from index {start_index}. Processing {len(urls_to_process)} properties.",
        "magenta",
    )

    token_cache = {"token": None, "expires_at": None}

    async with httpx.AsyncClient() as client:
        for i, url in enumerate(urls_to_process, start=start_index + 1):
            print_color(f"\n--- Processing {i}/{len(all_urls)}: {url} ---", "yellow")

            if not token_cache.get("token") or datetime.now(
                timezone.utc
            ) >= token_cache["expires_at"] - timedelta(seconds=60):
                print_color(
                    "Token is missing or expired. Fetching a new one...", "magenta"
                )
                # Add a small delay before fetching a new token to allow rate limiter to cool down
                await asyncio.sleep(1)
                token_data = await get_auth_token(client)
                if not token_data:
                    print_color("Could not authenticate. Skipping property.", "red")
                    continue
                token_cache = token_data

            auth_token = token_cache["token"]

            scrape_super_id = await get_super_id(
                client, auth_token, f"Backfill scrape for URL: {url}"
            )
            if not scrape_super_id:
                print_color(f"  - ⚠️ SKIPPED: Could not get super_id.", "yellow")
                continue

            await trigger_detailed_scrape(client, url, scrape_super_id)
            await asyncio.sleep(2)

    print_color("\n🎉 Backfill scraping process complete! 🎉", "green")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape a list of missing properties from a CSV."
    )
    parser.add_argument(
        "file_path", help="Path to the CSV file containing property URLs."
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="0-based index to start processing from.",
    )
    args = parser.parse_args()

    asyncio.run(main(args.file_path, args.start_index))
