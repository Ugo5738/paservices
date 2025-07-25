# scrip.py
import argparse
import csv
import math
import os
import re  # Import the regular expressions module
import time

import requests


def setup_arg_parser():
    """Sets up the argument parser for the property search script."""
    parser = argparse.ArgumentParser(
        description="Search for properties on Rightmove and save to CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Required parameter
    parser.add_argument(
        "--identifier",
        type=str,
        required=True,
        help="Location identifier from auto-complete endpoint (e.g., 'REGION^1036').",
    )

    # Optional parameters from the API
    parser.add_argument(
        "--sort-by",
        type=str,
        choices=["HighestPrice", "LowestPrice", "NewestListed"],
        help="Sort order of the results.",
    )
    parser.add_argument(
        "--search-radius",
        type=float,
        choices=[
            0.0,
            0.25,
            0.5,
            1.0,
            3.0,
            5.0,
            10.0,
            15.0,
            20.0,
            30.0,
            40.0,
        ],
        help="Search radius in miles.",
    )
    parser.add_argument("--min-price", type=int, help="Minimum property price.")
    parser.add_argument("--max-price", type=int, help="Maximum property price.")
    parser.add_argument("--min-bedroom", type=int, help="Minimum number of bedrooms.")
    parser.add_argument("--max-bedroom", type=int, help="Maximum number of bedrooms.")
    parser.add_argument(
        "--property-type",
        type=str,
        help="Comma-separated list of property types (e.g., 'Detached,SemiDetached,Flat').",
    )
    parser.add_argument(
        "--added-to-site",
        type=int,
        choices=[1, 3, 7, 14],
        help="Filter by days since added to site (1=24h, 3=3days, 7=7days, 14=14days).",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        help="Comma-separated list of keywords to search for (e.g., 'pool,garden').",
    )

    # Boolean-like string parameters
    boolean_params = [
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
    ]
    for param in boolean_params:
        parser.add_argument(
            f'--{param.replace("_", "-")}',
            type=str,
            choices=["true", "false"],
            help=f"Set boolean filter for '{param}'.",
        )

    return parser


def build_querystring_from_args(args):
    """Builds the querystring dictionary from parsed command-line arguments."""
    query = {}
    args_dict = vars(args)

    for key, value in args_dict.items():
        if value is not None:
            # The argparse dest names match the API query param names
            query[key] = value

    # The API expects search_radius as a string with one decimal place.
    if "search_radius" in query:
        query["search_radius"] = f"{query['search_radius']:.1f}"

    return query


# --- Request Configuration ---

# The base URL for the API endpoint
url = "https://uk-real-estate-rightmove.p.rapidapi.com/buy/property-for-sale"

# The headers required by the API
headers = {
    "x-rapidapi-host": "uk-real-estate-rightmove.p.rapidapi.com",
    # "x-rapidapi-key": "f4adffc4dbmsh8f530f1ac9b4b1ep11e20djsn17b8fc732bab", # It's good practice to not save keys in code
    "x-rapidapi-key": "4a47379444mshf60622395608b0cp1c90dajsn417082900379",
}


# --- Analysis function ---
def analyze_results(csv_filename, all_properties_list, total_results_count):
    """Analyzes the results from the CSV and the API fetch."""
    print("\n--- Analyzing Results from CSV ---")

    try:
        with open(csv_filename, mode="r", encoding="utf-8") as file:
            reader = list(csv.reader(file))
    except FileNotFoundError:
        print(f"Error: The file '{csv_filename}' was not found.")
        return

    header = reader[0]
    rows = reader[1:]
    total_entries = len(rows)

    if total_entries == 0:
        print("The CSV file is empty.")
        return

    seen_ids = set()
    seen_addresses = set()
    for row in rows:
        if not row:
            continue
        property_url = row[0]
        property_address = row[3]
        match = re.search(r"/(\d+)", property_url)
        if match:
            property_id = match.group(1)
            seen_ids.add(property_id)
        seen_addresses.add(property_address)

    print(f"Total entries in CSV: {total_entries}")
    print("-" * 20)
    unique_id_count = len(seen_ids)
    duplicate_id_count = total_entries - unique_id_count
    print("Analysis by Property ID (from URL):")
    print(f"  - Unique Properties: {unique_id_count}")
    print(f"  - Duplicate Listings (same ID): {duplicate_id_count}")
    print("-" * 20)
    unique_address_count = len(seen_addresses)
    duplicate_address_count = total_entries - unique_address_count
    print("Analysis by Full Address String:")
    print(f"  - Unique Addresses: {unique_address_count}")
    print(f"  - Duplicate Listings (same address): {duplicate_address_count}")
    print(
        "(Note: Minor differences like 'London' vs 'Wandsworth' count as unique addresses)"
    )
    print("-" * 20)

    # Explain the discrepancy
    if total_results_count > 0 and len(all_properties_list) != total_results_count:
        print("\nAPI Discrepancy Report:")
        print(f"- The API reported {total_results_count} total results.")
        print(
            f"- We actually collected {len(all_properties_list)} properties across all pages."
        )
        print(
            "- This confirms the API either returns duplicate listings across pages or provides an inaccurate initial count."
        )


# --- Main script logic ---
if __name__ == "__main__":
    parser = setup_arg_parser()
    args = parser.parse_args()

    # Build the base querystring from command-line arguments
    base_querystring = build_querystring_from_args(args)

    # --- Configuration ---
    CSV_FILENAME = "properties2.csv"
    PROPERTIES_TO_FETCH = 20  # 5000 in original
    all_properties = []
    total_results = 0

    print("--- Starting Intelligent Property Fetch ---")
    print(f"Search Criteria: {base_querystring}")

    try:
        # 1. Make the initial request for page 1 to get metadata
        print("Fetching page 1 to get total count...")
        initial_querystring = base_querystring.copy()
        initial_querystring["page"] = 1

        response = requests.get(url, headers=headers, params=initial_querystring)
        response.raise_for_status()
        initial_data = response.json()

        properties_on_page = initial_data.get("data")
        if not properties_on_page:
            print("No properties found on the first page. Exiting.")
            exit()

        all_properties.extend(properties_on_page)

        # 2. Calculate the total number of pages needed
        total_results = initial_data.get("totalResultCount", 0)
        per_page = initial_data.get("resultsPerPage", 25)

        if total_results > 0:
            total_pages = math.ceil(total_results / per_page)
            print(
                f"Total properties available: {total_results}. Total pages: {total_pages}"
            )
        else:
            total_pages = 1

        # 3. Loop through the *remaining* pages
        for page_num in range(2, total_pages + 1):
            if len(all_properties) >= PROPERTIES_TO_FETCH:
                print(
                    f"\nTarget of {PROPERTIES_TO_FETCH} properties reached. Stopping fetch."
                )
                break

            print(f"Fetching page {page_num} of {total_pages}...")
            querystring = base_querystring.copy()
            querystring["page"] = page_num

            response = requests.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            page_data = response.json()

            properties_on_page = page_data.get("data")
            if properties_on_page:
                all_properties.extend(properties_on_page)

            time.sleep(0.5)

        # 4. Write all collected data to the CSV
        if all_properties:
            final_properties = all_properties[:PROPERTIES_TO_FETCH]
            print(
                f"\nTotal properties collected: {len(final_properties)}. Writing to {CSV_FILENAME}..."
            )

            with open(CSV_FILENAME, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Full URL", "Price (GBP)", "Bedrooms", "Address"])

                for prop in final_properties:
                    price = prop.get("price", {}).get("amount")
                    bedrooms = prop.get("bedrooms")
                    address = prop.get("displayAddress", "").strip()
                    relative_url = prop.get("propertyUrl")
                    full_url = (
                        f"https://www.rightmove.co.uk{relative_url}"
                        if relative_url
                        else "URL not found"
                    )
                    writer.writerow([full_url, price, bedrooms, address])

            print(f"Finished. Data has been saved to '{CSV_FILENAME}'")

    except requests.exceptions.HTTPError as errh:
        print(f"Http Error: {errh}")
        if "response" in locals() and hasattr(response, "text"):
            print(f"Response content: {response.text}")
    except requests.exceptions.RequestException as err:
        print(f"An unexpected error occurred: {err}")
    except Exception as e:
        print(f"A general error occurred: {e}")

    # Call the analysis function at the end
    analyze_results(CSV_FILENAME, all_properties, total_results)


# # Basic search (required identifier):
# python scrip.py --identifier "REGION^87490"

# # Search for 3-bedroom houses in a 5-mile radius:
# python scrip.py --identifier "REGION^87490" --search-radius 5.0 --min-bedroom 3 --max-bedroom 3 --property-type "Detached,SemiDetached,Terraced"

# # Search for properties with a garden and parking, added in the last 7 days:
# python scrip.py --identifier "REGION^1036" --min-price 500000 --max-price 750000 --sort-by NewestListed
