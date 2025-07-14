import csv
import math
import os
import re  # Import the regular expressions module
import time

import requests

# --- Request Configuration ---

# The base URL for the API endpoint
url = "https://uk-real-estate-rightmove.p.rapidapi.com/buy/property-for-sale"

# The headers required by the API
headers = {
    "x-rapidapi-host": "uk-real-estate-rightmove.p.rapidapi.com",
    # "x-rapidapi-key": "f4adffc4dbmsh8f530f1ac9b4b1ep11e20djsn17b8fc732bab", # It's good practice to not save keys in code
    "x-rapidapi-key": "f846d19a60msh2784c2ba0508745p1f0be3jsn2676a9a367f6",
}

# The base query parameters, without the page number
base_querystring = {
    "identifier": "STATION^506",
    "sort_by": "HighestPrice",
    "search_radius": "1.0",
}

# --- Configuration ---
CSV_FILENAME = "properties2.csv"
PROPERTIES_TO_FETCH = 20  # 5000
all_properties = []
total_results = 0  # Define it in the global scope

# --- Main script logic ---
print("--- Starting Intelligent Property Fetch ---")

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
    print(f"Response content: {response.text}")
except requests.exceptions.RequestException as err:
    print(f"An unexpected error occurred: {err}")


# --- NEW AND IMPROVED ANALYSIS FUNCTION ---
def analyze_results():
    print("\n--- Analyzing Results from CSV ---")

    try:
        with open(CSV_FILENAME, mode="r", encoding="utf-8") as file:
            reader = list(csv.reader(file))
    except FileNotFoundError:
        print(f"Error: The file '{CSV_FILENAME}' was not found.")
        return

    # The total number of rows in the CSV, excluding the header
    header = reader[0]
    rows = reader[1:]
    total_entries = len(rows)

    if total_entries == 0:
        print("The CSV file is empty.")
        return

    # Use sets to efficiently find unique items
    seen_ids = set()
    seen_addresses = set()

    for row in rows:
        if not row:
            continue

        property_url = row[0]
        property_address = row[3]

        # Use regular expression to reliably find the property ID (a sequence of numbers)
        match = re.search(r"/(\d+)", property_url)
        if match:
            property_id = match.group(1)
            seen_ids.add(property_id)

        seen_addresses.add(property_address)

    # --- Print Clear, Meaningful Results ---
    print(f"Total entries in CSV: {total_entries}")
    print("-" * 20)

    # Analysis based on Property ID
    unique_id_count = len(seen_ids)
    duplicate_id_count = total_entries - unique_id_count
    print(f"Analysis by Property ID (from URL):")
    print(f"  - Unique Properties: {unique_id_count}")
    print(f"  - Duplicate Listings (same ID): {duplicate_id_count}")

    print("-" * 20)

    # Analysis based on Address
    unique_address_count = len(seen_addresses)
    duplicate_address_count = total_entries - unique_address_count
    print(f"Analysis by Full Address String:")
    print(f"  - Unique Addresses: {unique_address_count}")
    print(f"  - Duplicate Listings (same address): {duplicate_address_count}")
    print(
        "(Note: Minor differences like 'London' vs 'Wandsworth' count as unique addresses)"
    )

    print("-" * 20)

    # Explain the discrepancy
    if len(all_properties) != total_results and total_results > 0:
        print(f"\nAPI Discrepancy Report:")
        print(f"- The API reported {total_results} total results.")
        print(
            f"- We actually collected {len(all_properties)} properties across all pages."
        )
        print(
            "- This confirms the API either returns duplicate listings across pages or provides an inaccurate initial count."
        )


# Call the new function
analyze_results()
