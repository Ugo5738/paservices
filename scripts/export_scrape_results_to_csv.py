# /paservices/scripts/export_scrape_results_to_csv.py
import argparse
import asyncio
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx

# --- Configuration (for local execution) ---
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
DATA_CAPTURE_SERVICE_URL = os.getenv(
    "DATA_CAPTURE_RIGHTMOVE_SERVICE_URL", "http://localhost:8003"
)
M2M_CLIENT_ID = os.getenv("M2M_CLIENT_ID", "fe2c7655-0860-4d98-9034-cd5e1ac90a41")
M2M_CLIENT_SECRET = os.getenv("M2M_CLIENT_SECRET", "dev-rightmove-service-secret")


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


async def fetch_scraped_data_and_build_map(
    client: httpx.AsyncClient, token: str, days_to_check: int = 5
) -> Dict[str, str]:
    print_color(
        f"▶ Fetching scraped properties from the last {days_to_check} days to build a lookup map...",
        "blue",
    )
    url = f"{DATA_CAPTURE_SERVICE_URL}/api/v1/properties/scraped-listings"
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

    url_map = {}
    for prop in all_properties:
        if prop.get("property_url"):
            relative_url = prop["property_url"]
            if "http" in relative_url:
                relative_url = "/" + "/".join(relative_url.split("/")[3:])
            clean_url = f"https://www.rightmove.co.uk{relative_url}".split("#")[0]
            url_map[clean_url] = prop["super_id"]

    print_color(f"✅ Built lookup map with {len(url_map)} unique, clean URLs.", "green")
    return url_map


async def main(csv_path: str, output_path: str):
    print_color("🚀 Starting Workflow to Export Scrape Results 🚀", "yellow")

    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            target_urls = {row["full_url"].split("#")[0] for row in reader}
    except FileNotFoundError:
        print_color(f"❌ ERROR: The input file '{csv_path}' was not found.", "red")
        return
    except KeyError:
        print_color(
            "❌ ERROR: Input CSV must have a header column named 'full_url'.", "red"
        )
        return

    async with httpx.AsyncClient() as client:
        internal_token = await get_internal_auth_token(client)
        if not internal_token:
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
                "Could not find a match between the CSV and any recently scraped properties.",
                "red",
            )
            return

        results_to_write = []
        for url in urls_to_process:
            super_id = url_to_super_id_map.get(url)
            if super_id:
                results_to_write.append(
                    {"Property_URL": url, "Scrape_Super_ID": super_id}
                )

        try:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["Property_URL", "Scrape_Super_ID"]
                )
                writer.writeheader()
                writer.writerows(results_to_write)
            print_color(
                f"\n✅ Successfully exported {len(results_to_write)} matching properties to '{output_path}'.",
                "green",
            )
        except Exception as e:
            print_color(
                f"❌ ERROR: Failed to write to output file '{output_path}'. Details: {e}",
                "red",
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export scrape results for a list of property URLs to a CSV file."
    )
    parser.add_argument("csv_path", help="Path to the input CSV file of property URLs.")
    parser.add_argument("output_path", help="Path for the output CSV file.")
    args = parser.parse_args()

    asyncio.run(main(args.csv_path, args.output_path))
