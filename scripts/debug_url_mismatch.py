# /paservices/scripts/debug_url_mismatch.py
import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx

print("checking")
# --- Configuration (for local execution) ---
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
DATA_CAPTURE_SERVICE_URL = os.getenv(
    "DATA_CAPTURE_RIGHTMOVE_SERVICE_URL", "http://localhost:8003"
)
M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")


def print_color(text, color):
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


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


async def fetch_scraped_urls(client: httpx.AsyncClient, token: str) -> List[str]:
    print_color("▶ Fetching scraped property URLs from the API...", "blue")
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/scraped-listings"
    headers = {"Authorization": f"Bearer {token}"}
    all_properties = []

    for i in range(5):  # Check last 5 days
        check_date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime(
            "%Y-%m-%d"
        )
        params = {"on_date": check_date, "limit": 5000}
        try:
            response = await client.get(
                url, headers=headers, params=params, timeout=120
            )
            response.raise_for_status()
            properties = response.json().get("properties", [])
            if properties:
                all_properties.extend(properties)
        except Exception:
            pass  # Ignore errors for this debug script

    return [
        f"https://www.rightmove.co.uk{prop['property_url']}"
        for prop in all_properties
        if prop.get("property_url")
    ]


async def main(csv_path: str):
    print_color("🚀 Starting URL Mismatch Debugger 🚀", "yellow")

    # 1. Read URLs from CSV
    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            csv_urls = {row["full_url"] for row in reader}
    except Exception as e:
        print_color(f"❌ ERROR reading CSV file: {e}", "red")
        return

    # 2. Fetch URLs from the API
    api_urls = set()
    async with httpx.AsyncClient() as client:
        internal_token = await get_internal_auth_token(client)
        if internal_token:
            api_urls = set(await fetch_scraped_urls(client, internal_token))

    # 3. Print raw samples for direct comparison
    print_color("\n--- Comparing Raw URLs (First 5 Samples) ---", "magenta")
    print_color("--- URLs from CSV file ---", "yellow")
    for i, url in enumerate(list(csv_urls)[:5]):
        print(f"[{i}]: '{url}'")

    print_color("\n--- URLs from API ---", "yellow")
    if api_urls:
        for i, url in enumerate(list(api_urls)[:5]):
            print(f"[{i}]: '{url}'")
    else:
        print_color("Could not fetch any URLs from the API.", "red")

    # 4. Normalize and check for matches
    print_color("\n--- Comparing Normalized URLs ---", "magenta")
    normalized_csv_urls = {url.split("#")[0].strip() for url in csv_urls}
    normalized_api_urls = {url.split("#")[0].strip() for url in api_urls}

    print(f"Found {len(normalized_csv_urls)} unique normalized URLs in CSV.")
    print(f"Found {len(normalized_api_urls)} unique normalized URLs in API results.")

    intersection = normalized_csv_urls.intersection(normalized_api_urls)

    print_color(
        f"\nFound {len(intersection)} matches after normalization.",
        "green" if intersection else "red",
    )
    if intersection:
        print_color("Sample of matching URLs:", "yellow")
        for i, url in enumerate(list(intersection)[:5]):
            print(f" - '{url}'")

    if not intersection:
        print_color(
            "\nCONCLUSION: The base URLs are fundamentally different even after normalization.",
            "red",
        )
        print_color(
            "Please carefully compare the samples above for subtle differences (e.g., http vs https, www vs non-www, trailing slashes).",
            "yellow",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Debug URL mismatches between CSV and API."
    )
    parser.add_argument("csv_path", help="Path to the CSV file of property URLs.")
    args = parser.parse_args()
    asyncio.run(main(args.csv_path))
