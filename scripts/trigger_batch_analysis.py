#!/usr/bin/env python3
"""
Command-line script to trigger property analysis workflows in a batch.

This script reads a list of property URLs from a JSON file and calls the
analysis endpoint for each one, simulating multiple users or a batch job.
It is designed to interact with an orchestration service like the one provided.

Usage:
  - To run a full batch analysis:
    python scripts/trigger_batch_analysis.py /path/to/your/properties.json --phone-number="+447123456789"

  - To do a dry run without making API calls:
    python scripts/trigger_batch_analysis.py /path/to/your/properties.json --phone-number="+447123456789" --dry-run

  - To resume a batch from the 10th item with a 5-minute delay:
    python scripts/trigger_batch_analysis.py /path/to/your/properties.json --phone-number="+447123456789" --start-index=9 --delay=300
"""

import argparse
import json
import os
import sys
import time

import requests
from requests.exceptions import RequestException

# --- Configuration ---
# The target API endpoint, configurable via environment variable or default.
ORCHESTRATION_API_URL = os.getenv(
    "ORCHESTRATION_API_URL",
    "https://api.supersami.com/api/orchestration/properties/analyze/",
)
# Default delay in seconds between each API call.
DEFAULT_DELAY_SECONDS = 10


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


def main():
    """Main function to parse arguments and orchestrate the batch workflow."""
    parser = argparse.ArgumentParser(
        description="Trigger property analysis workflows in batch."
    )
    parser.add_argument(
        "json_file", type=str, help="Path to the JSON file containing property URLs."
    )
    parser.add_argument(
        "--phone-number",
        type=str,
        required=True,
        help="The phone number to associate with these analysis tasks.",
    )
    parser.add_argument(
        "--api-token",
        type=str,
        required=True,
        help="The authentication token for the API.",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Delay in seconds between triggers (default: {DEFAULT_DELAY_SECONDS}).",
    )
    parser.add_argument(
        "--analysis-source",
        type=str,
        default="original",
        help="Value for the 'analysis_source' field (e.g., 'email').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the process without making API calls.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="0-based index of the item to start processing from.",
    )

    args = parser.parse_args()

    # --- Validate Inputs ---
    if not os.path.exists(args.json_file):
        raise CommandError(f"Error: JSON file not found at '{args.json_file}'")
    if args.start_index < 0:
        args.start_index = 0
        print_color("Start index cannot be negative. Starting from 0.", "yellow")

    # --- Load JSON Data ---
    print_color(f"Loading properties from: {args.json_file}", "blue")
    with open(args.json_file, "r", encoding="utf-8") as f:
        properties_data = json.load(f)

    if not isinstance(properties_data, list):
        raise CommandError("Error: JSON file content must be a list of objects.")

    total_properties = len(properties_data)
    if args.start_index >= total_properties:
        print_color(
            f"Start index ({args.start_index}) is beyond the end of the file ({total_properties} items). Nothing to process.",
            "yellow",
        )
        return

    properties_to_process = properties_data[args.start_index :]
    print_color(
        f"Found {total_properties} total properties. Attempting to process {len(properties_to_process)} starting from index {args.start_index}.",
        "magenta",
    )

    if args.dry_run:
        print_color("DRY RUN MODE IS ENABLED. NO API CALLS WILL BE MADE.", "yellow")

    # --- Process Each Property ---
    success_count = 0
    error_count = 0
    headers = {"Authorization": f"Bearer {args.api_token}"}

    for i, property_item in enumerate(properties_to_process):
        current_index = args.start_index + i
        print("-" * 20)
        print_color(
            f"Processing item {i+1}/{len(properties_to_process)} (Original Index: {current_index})...",
            "blue",
        )

        if not isinstance(property_item, dict) or "url" not in property_item:
            print_color(
                f"  ❌ Skipping item: Invalid format or missing 'url' key.", "red"
            )
            error_count += 1
            continue

        property_url = property_item["url"]
        print(f"  URL: {property_url}")

        payload = {
            "url": property_url,
            "phone_number": args.phone_number,
            "analysis_source": args.analysis_source,
            "perform_scrape": True,
            "perform_analysis": True,
        }

        if not args.dry_run:
            try:
                response = requests.post(
                    ORCHESTRATION_API_URL, json=payload, headers=headers, timeout=30
                )
                response.raise_for_status()
                print_color(
                    f"  ✅ Successfully triggered analysis. Status: {response.status_code}. Response: {response.json()}",
                    "green",
                )
                success_count += 1
            except RequestException as e:
                print_color(f"  ❌ API Error for URL {property_url}: {e}", "red")
                if e.response is not None:
                    print_color(f"     Response Body: {e.response.text}", "red")
                error_count += 1
            except Exception as e:
                print_color(
                    f"  ❌ An unexpected error occurred for URL {property_url}: {e}",
                    "red",
                )
                error_count += 1
        else:
            print_color(f"  [DRY RUN] Would send payload: {payload}", "yellow")
            success_count += 1

        # Delay before processing the next item
        if i < len(properties_to_process) - 1 and args.delay > 0:
            print(f"  Waiting for {args.delay} seconds...")
            try:
                time.sleep(args.delay)
            except KeyboardInterrupt:
                print_color("\nCommand interrupted by user. Exiting.", "yellow")
                next_start_index = current_index
                print_color(
                    f"To resume, use --start-index={next_start_index}", "yellow"
                )
                sys.exit(0)

    # --- Final Summary ---
    print("\n" + "=" * 20)
    print_color("Batch Processing Complete", "magenta")
    print(f"Total properties processed: {success_count + error_count}")
    print_color(f"Successful triggers: {success_count}", "green")
    print_color(f"Failed triggers: {error_count}", "red")
    print("=" * 20)


if __name__ == "__main__":
    main()
