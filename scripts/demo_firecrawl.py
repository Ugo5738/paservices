import argparse
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from pydantic import BaseModel

# Five sample UK property listing pages to try out of the box.
DEFAULT_URLS: list[str] = [
    "https://www.rightmove.co.uk/properties/150432377#/?channel=RES_BUY",
    "https://www.zoopla.co.uk/for-sale/details/71531651/",
    "https://www.onthemarket.com/details/16578037/",
    "https://www.primelocation.com/to-rent/details/71219657/",
    "https://search.savills.com/property-detail/gbwarswas230015",
]

PROPERTY_SCHEMA: dict[str, Any] = {
    "url": {"type": "string", "description": "Listing URL you scraped."},
    "address": {"type": "string", "description": "Full postal address if present."},
    "postcode": {"type": "string", "description": "UK postcode if present."},
    "price": {
        "type": "object",
        "properties": {
            "raw": {"type": "string", "description": "Price exactly as shown."},
            "value": {"type": "number", "description": "Numeric value if parsable."},
            "currency": {
                "type": "string",
                "description": "ISO code if obvious, else null.",
            },
            "frequency": {
                "type": "string",
                "enum": ["sale", "weekly", "monthly", "yearly", "unknown"],
            },
        },
        "required": ["raw"],
    },
    "listing_type": {"type": "string", "enum": ["sale", "rent", "unknown"]},
    "property_type": {
        "type": "string",
        "enum": [
            "detached",
            "semi-detached",
            "terraced",
            "end-terrace",
            "flat",
            "apartment",
            "maisonette",
            "bungalow",
            "cottage",
            "studio",
            "house",
            "unknown",
        ],
    },
    "bedrooms": {"type": "integer"},
    "bathrooms": {"type": "integer"},
    "tenure": {
        "type": "string",
        "enum": ["freehold", "leasehold", "share-of-freehold", "unknown"],
    },
    "description": {"type": "string"},
    "features": {"type": "array", "items": {"type": "string"}},
    "agent": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "phone": {"type": "string"},
            "email": {"type": "string"},
            "website": {"type": "string"},
        },
    },
}

DEFAULT_JSON_PROMPT = (
    "Extract property details into the schema. "
    "Map property_type to the closest enum. "
    "Set listing_type to 'sale' or 'rent' if obvious else 'unknown'. "
    "Use price.raw exactly as displayed; fill price.value and price.currency if obvious; "
    "set price.frequency to sale/weekly/monthly/yearly/unknown. "
    "Do not fabricate missing values; leave fields null when absent."
)


def parse_formats(raw_formats: str) -> list[str]:
    parts = [fmt.strip() for fmt in raw_formats.split(",") if fmt.strip()]
    if not parts:
        raise argparse.ArgumentTypeError(
            "Provide at least one format (e.g. json,html)."
        )
    return parts


def serialize_result(result: Any) -> Any:
    if isinstance(result, BaseModel):
        return result.model_dump(exclude_none=True)
    if isinstance(result, dict):
        return {k: v for k, v in result.items() if v is not None}
    return result


def unique_preserve_order(items: Iterable[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def gather_urls(args: argparse.Namespace) -> list[str]:
    urls: List[str] = []

    if args.urls:
        urls.extend([u.strip() for u in args.urls.split(",") if u.strip()])
    if args.url:
        urls.append(args.url.strip())
    if args.urls_file:
        try:
            with open(args.urls_file, "r", encoding="utf-8") as f:
                urls.extend([line.strip() for line in f if line.strip()])
        except OSError as exc:
            sys.exit(f"Failed to read urls file: {exc}")

    urls = unique_preserve_order(urls)
    return urls or DEFAULT_URLS


def build_formats(args: argparse.Namespace) -> list[Any]:
    formats = parse_formats(args.formats)
    if any(fmt.lower() == "json" for fmt in formats) and not args.json_extract:
        print(
            "Ignoring plain 'json' format because no prompt/schema provided; enable --json-extract to include structured JSON.",
            file=sys.stderr,
        )
        formats = [fmt for fmt in formats if fmt.lower() != "json"]

    if args.json_extract:
        formats = [fmt for fmt in formats if fmt.lower() != "json"]
        formats.append(
            {
                "type": "json",
                "prompt": args.json_prompt or DEFAULT_JSON_PROMPT,
                "schema": PROPERTY_SCHEMA,
            }
        )

    return formats


def normalize_price(price: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(price, dict):
        return price
    raw = price.get("raw") or ""
    value = price.get("value")
    if value is None:
        match = re.search(r"[0-9][0-9,\\.]*", raw.replace(",", ""))
        if match:
            try:
                value = float(match.group(0))
            except ValueError:
                value = None
    norm = dict(price)
    if value is not None:
        norm["value"] = value
    return norm


def extract_property_fields(markdown: str, url: str) -> dict[str, Any]:
    """Lightweight, best-effort parsing from markdown when JSON extract is unavailable."""
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    text = " ".join(lines)
    lower = text.lower()

    price_match = re.search(r"£\s?[0-9][0-9,\\.]*", text)
    bed_match = re.search(r"(\\d+)\\s+bed(?:room)?s?", lower)
    bath_match = re.search(r"(\\d+)\\s+bath(?:room)?s?", lower)

    property_types = [
        "detached",
        "semi-detached",
        "terraced",
        "end of terrace",
        "flat",
        "apartment",
        "maisonette",
        "bungalow",
        "cottage",
        "house",
        "studio",
    ]
    property_type = next((pt for pt in property_types if pt in lower), None)

    tenure = None
    if "freehold" in lower:
        tenure = "freehold"
    elif "leasehold" in lower:
        tenure = "leasehold"

    address = next(
        (
            line
            for line in lines[:40]
            if any(
                part in line.lower()
                for part in [
                    " road",
                    " street",
                    " lane",
                    " avenue",
                    " drive",
                    " city",
                    "town",
                    "village",
                ]
            )
            or "," in line
        ),
        None,
    )

    feature_lines = [
        line
        for line in lines
        if line.startswith(("-", "•", "*")) or re.match(r"^[A-Z].+\\.$", line)
    ]
    features = feature_lines[:12] if feature_lines else None

    return {
        "url": url,
        "price": price_match.group(0) if price_match else None,
        "address": address,
        "bedrooms": int(bed_match.group(1)) if bed_match else None,
        "bathrooms": int(bath_match.group(1)) if bath_match else None,
        "property_type": property_type,
        "tenure": tenure,
        "agent": None,
        "features": features,
    }


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run a Firecrawl scrape.")
    parser.add_argument(
        "--url",
        help="Single URL to scrape (can be combined with --urls/--urls-file).",
    )
    parser.add_argument(
        "--urls",
        help="Comma-separated list of URLs to scrape.",
    )
    parser.add_argument(
        "--urls-file",
        help="File with one URL per line.",
    )
    parser.add_argument(
        "--formats",
        default="markdown,html,json",
        help="Comma-separated output formats (e.g. markdown,html,links,json).",
    )
    parser.add_argument(
        "--json-extract",
        action="store_true",
        default=True,
        help="Include structured JSON extraction for property details using a preset prompt/schema (default on).",
    )
    parser.add_argument(
        "--no-json-extract",
        action="store_false",
        dest="json_extract",
        help="Disable structured JSON extraction.",
    )
    parser.add_argument(
        "--json-prompt",
        help="Optional custom prompt for JSON extraction.",
    )
    parser.add_argument(
        "--output",
        default="output/firecrawl_properties.json",
        help="File path to write the aggregated JSON response.",
    )
    args = parser.parse_args()

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        sys.exit("Set FIRECRAWL_API_KEY in your environment or .env file.")

    urls = gather_urls(args)
    formats = build_formats(args)
    app = FirecrawlApp(api_key=api_key)

    results = []
    for url in urls:
        try:
            result = app.scrape(
                url=url,
                formats=formats,
                only_main_content=True,
            )
            payload = serialize_result(result)
            if isinstance(payload, dict):
                if "json" in payload and isinstance(payload["json"], dict):
                    payload["json"] = {
                        **payload["json"],
                        "price": normalize_price(payload["json"].get("price")),
                    }
                if isinstance(payload.get("markdown"), str):
                    payload["extracted"] = extract_property_fields(
                        payload["markdown"], url
                    )
            results.append({"url": url, "success": True, "data": payload})
        except Exception as exc:
            results.append({"url": url, "success": False, "error": str(exc)})

    aggregated = {"results": results}

    if args.output:
        try:
            os.makedirs(os.path.dirname(args.output), exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(aggregated, f, indent=2)
        except OSError as exc:
            sys.exit(f"Failed to write output file: {exc}")

    print(json.dumps(aggregated, indent=2))


if __name__ == "__main__":
    main()
