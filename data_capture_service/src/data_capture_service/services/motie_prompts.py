"""
Motie agent prompt templates for build and repair sessions.

Centralizing the prompts here keeps them out of router code and makes them easy
to iterate on without touching control flow.
"""

from typing import Any, Dict, Optional

# Default field list — the schema we want every coded property fetcher to extract.
# Mirrors the Motie adapter's DEFAULT_MOTIE_PROMPT for parity with the existing
# adapter's expectations.
PROPERTY_FIELDS = (
    "Address (Road name), Floorplan(s) Images URL(s), Image(s) URL(s) (ALL, High Res), "
    "Source URL, Price, Address (Town), Bedrooms (number), Estate Agent Name, "
    "Estate Agent Address, Transaction Type Details, Bathrooms (number), "
    "Type (House, Detached etc), Created (came to market), Address (full), "
    "Address (Postcode), Description (Full), Rightmove URL, Description (Short), "
    "Size, Tenure, Garden, Parking, Address (Location Coordinates), "
    "Status/Availability, Last Update & Reason, EPC(s), Train Station (nearby), "
    "Video(s) URLs, Access, Accessibility, Flood Risk, Heating, Listed?, "
    "Restrictions, Shared Ownership, Utilities"
)


def build_initial_prompt(
    url: str,
    benchmark_fields: Optional[Dict[str, Any]] = None,
    extra_context: Optional[str] = None,
) -> str:
    """
    Prompt for an initial build (Flow A — first scraper for this domain).

    benchmark_fields, when supplied, are AI-fetcher (e.g. Firecrawl) results
    that show what data the page actually contains — gives the agent a
    concrete extraction target.
    """
    sections = [
        f"Target URL: {url}",
        "",
        "Build a FastAPI scraper for this property listing website. "
        "The scraper should accept a `listing_url` query parameter and extract "
        "all property details from the page at that URL.",
        "",
        "Extract these fields and return them as a JSON object. "
        "If a detail isn't present on the page, put null as the value:",
        "",
        PROPERTY_FIELDS,
    ]

    if benchmark_fields:
        present = [k for k, v in benchmark_fields.items() if v]
        if present:
            sections.append("")
            sections.append(
                "Reference data: an independent extractor confirmed these fields ARE "
                f"present on this URL: {present}. Your scraper must extract all of them."
            )

    if extra_context:
        sections.append("")
        sections.append(extra_context)

    return "\n".join(sections)


def build_repair_prompt(
    url: str,
    failing_error: str,
    missing_fields: Optional[Any] = None,
    benchmark_fields: Optional[Dict[str, Any]] = None,
    extra_context: Optional[str] = None,
) -> str:
    """
    Prompt for a repair session on an existing project (Flow E — fix broken scraper).

    Emphasizes that the agent has access to the prior code in the project and
    should fix it rather than rewrite from scratch.
    """
    sections = [
        f"The deployed scraper for this domain is failing.",
        "",
        f"Failing URL: {url}",
        f"Error: {failing_error}",
        "",
        "Please review the existing scraper code in this project, identify what's "
        "broken, and fix it so this URL extracts cleanly.",
        "",
        "The scraper should accept a `listing_url` query parameter and extract "
        "all property details from the page. Return a JSON object with these fields "
        "(null where not present):",
        "",
        PROPERTY_FIELDS,
    ]

    if missing_fields:
        sections.append("")
        sections.append(
            f"Specific fields the previous run failed to capture: {list(missing_fields)}. "
            "Pay particular attention to extracting these correctly."
        )

    if benchmark_fields:
        present = [k for k, v in benchmark_fields.items() if v]
        if present:
            sections.append("")
            sections.append(
                f"Independent verification confirmed these fields ARE on the page: "
                f"{present}. Your fixed scraper must extract them."
            )

    if extra_context:
        sections.append("")
        sections.append(extra_context)

    return "\n".join(sections)
