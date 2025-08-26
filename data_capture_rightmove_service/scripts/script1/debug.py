#!/usr/bin/env python3
"""
Triggers a property search based on a comprehensive set of specified criteria.

This script authenticates with internal services, gets a super_id for the search batch,
and calls the data_capture_rightmove_service to start a background search task
with any of the 21 supported API parameters.
"""
import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

import httpx

# --- Configuration copied from your scripts ---
AUTH_SERVICE_URL = "http://auth_service:8000/api/v1"
SUPER_ID_SERVICE_URL = "http://super_id_service:8000/api/v1"
DATA_CAPTURE_RIGHTMOVE_SERVICE_URL = "http://data_capture_rightmove_service:8000/api/v1"

M2M_CLIENT_ID = "fe2c7655-0860-4d98-9034-cd5e1ac90a41"
M2M_CLIENT_SECRET = "dev-rightmove-service-secret"
# ---------------------------------------------


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


def setup_arg_parser() -> argparse.ArgumentParser:
    """Sets up the argument parser with all available search filters."""
    parser = argparse.ArgumentParser(
        description="Trigger a Rightmove property search with detailed criteria.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # --- Main Parameters ---
    parser.add_argument(
        "--identifier",
        required=True,
        help="Rightmove location identifier (e.g., 'REGION^87490' for London).",
    )
    parser.add_argument(
        "--num-properties",
        type=int,
        help="Total number of properties to retrieve by paginating through results.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the workflow without making the final search call.",
    )
    # --- Filtering Parameters ---
    parser.add_argument(
        "--sort-by",
        choices=[
            "HighestPrice",
            "LowestPrice",
            "NewestListed",
            "OldestListed",
            "NearestFirst",
        ],
        help="Sort order for the search results.",
    )
    parser.add_argument(
        "--search-radius",
        type=float,
        help="Search radius in miles (e.g., 0.0, 0.25, 0.5, 1.0, 3.0, etc.).",
    )
    parser.add_argument("--min-price", type=int, help="Minimum property price.")
    parser.add_argument("--max-price", type=int, help="Maximum property price.")
    parser.add_argument("--min-bedrooms", type=int, help="Minimum number of bedrooms.")
    parser.add_argument("--max-bedrooms", type=int, help="Maximum number of bedrooms.")
    parser.add_argument(
        "--property-type",
        help="Comma-separated property types (e.g., 'Detached,Flat').",
    )
    parser.add_argument(
        "--added-to-site",
        type=int,
        choices=[1, 3, 7, 14],
        help="Filter by days since added (1=24h, 3=3d, 7=7d, 14=14d).",
    )
    parser.add_argument(
        "--keywords", help="Comma-separated keywords (e.g., 'garden,pool')."
    )

    # --- Boolean Flags ---
    boolean_params = {
        "has_garden": "Include properties with gardens.",
        "has_new_home": "Include only new homes.",
        "has_buying_schemes": "Include properties with buying schemes.",
        "has_parking": "Include properties with parking.",
        "has_retirement_home": "Include retirement homes.",
        "has_auction_property": "Include auction properties.",
        "has_include_under_offer_sold_stc": "Include properties under offer/sold STC.",
        "do_not_show_new_home": "Exclude new homes from results.",
        "do_not_show_buying_schemes": "Exclude properties with buying schemes.",
        "do_not_show_retirement_home": "Exclude retirement homes.",
    }
    for param, help_text in boolean_params.items():
        # The command-line flag is derived from the parameter name.
        parser.add_argument(
            f'--{param.replace("_", "-")}',
            action="store_true",
            help=help_text,
            dest=param,  # Ensure argparse stores the value with the correct parameter name.
        )

    return parser


async def get_internal_auth_token(client: httpx.AsyncClient) -> Optional[str]:
    print_color("▶️  Step 1: Authenticating with INTERNAL Auth Service...", "blue")
    url = f"{AUTH_SERVICE_URL}/auth/token"
    print(f"Attempting to POST to: {url}")
    payload = {
        "grant_type": "client_credentials",
        "client_id": M2M_CLIENT_ID,
        "client_secret": M2M_CLIENT_SECRET,
    }
    try:
        response = await client.post(url, json=payload)

        if response.status_code == 200:
            print_color(
                "✅ Successfully received a token from the auth_service.", "green"
            )
            return response.json().get("access_token")
        else:
            print(f"⚠️  REQUEST FAILED! Status Code: {response.status_code}")
            print("   Response Body:")
            print(response.text)
            return None
    except Exception as e:
        print_color(f"❌ AUTHENTICATION FAILED. Error: {e}", "red")
        return None


async def get_super_id(
    client: httpx.AsyncClient, token: str, description: str
) -> Optional[str]:
    """Requests a Super ID for tracking the search workflow."""
    print_color(f"▶️  Step 2: Requesting Super ID for: '{description}'...", "blue")
    url = f"{SUPER_ID_SERVICE_URL}/super_ids"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"count": 1, "description": description}
    try:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        super_id = response.json().get("super_id")
        print_color(f"✅  SUCCESS: Super ID received: {super_id}", "green")
        return super_id
    except Exception as e:
        print_color(f"❌ ERROR: Could not get Super ID. Details: {e}", "red")
        if hasattr(e, "response"):
            print(e.response.text)
        return None


async def trigger_data_capture_rightmove_service_search(
    client: httpx.AsyncClient,
    token: str,
    search_super_id: str,
    args: argparse.Namespace,
) -> None:
    """Performs the data capture rightmove service search."""
    print_color(
        "▶️  Step 3: Triggering Data Capture Rightmove Service Search...", "blue"
    )
    url = f"{DATA_CAPTURE_RIGHTMOVE_SERVICE_URL}/properties/search/for-sale"
    headers = {"Authorization": f"Bearer {token}", "X-Super-ID": search_super_id}

    # Build payload from all provided arguments, handling booleans correctly.
    payload: Dict[str, Any] = {
        "location_identifier": args.identifier,
        "super_id": search_super_id,
    }

    args_dict = vars(args)

    # Define the keys that are boolean flags.
    boolean_keys = {
        "has_garden",
        "has_new_home",
        "has_buying_schemes",
        "has_parking",
        "has_retirement_home",
        "has_auction_property",
        "has_include_under_offer_sold_stc",
        "do_not_show_new_home",
        "do_not_show_buying_schemes",
        "do_not_show_retirement_home",
    }

    for key, value in args_dict.items():
        if key in boolean_keys:
            # For boolean flags from 'action="store_true"', the value will be True if present,
            # and False if absent. We only want to send the parameter if it's True.
            if value is True:
                payload[key] = True
        elif value is not None and key not in ["identifier", "dry_run"]:
            # For all other arguments, add them to the payload if they have a value.
            payload[key] = value

    if args.dry_run:
        print_color(
            "[DRY RUN] Would send the following payload to the search endpoint:",
            "yellow",
        )
        print(json.dumps(payload, indent=2))
        print_color("\n🎉 Dry run for search complete. 🎉", "green")
        sys.exit(0)

    try:
        response = await client.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        print_color(
            f"✅ SUCCESS: Search request for '{args.identifier}' accepted.", "green"
        )
        print("   Processing will continue in the background.")
    except httpx.HTTPStatusError as e:
        print_color(
            f"❌ ERROR: Search request failed with status {e.response.status_code}",
            "red",
        )
        print(f"   Response: {e.response.text}")
    except Exception as e:
        print_color(f"❌ ERROR: Could not trigger property search. Details: {e}", "red")


async def main():
    """Main function to parse arguments and trigger the property search."""
    parser = setup_arg_parser()
    args = parser.parse_args()

    print_color("🚀 Starting Property Search Workflow 🚀", "yellow")
    async with httpx.AsyncClient() as client:
        token = await get_internal_auth_token(client)
        if not token:
            sys.exit(1)

        search_super_id = await get_super_id(
            client, token, f"Search for location {args.identifier}"
        )
        if not search_super_id:
            sys.exit(1)

        await trigger_data_capture_rightmove_service_search(
            client, token, search_super_id, args
        )


if __name__ == "__main__":
    asyncio.run(main())
