"""
Motie agent prompt templates for build and repair sessions.

Centralizing the prompts here keeps them out of router code and makes them easy
to iterate on without touching control flow.

The wording mirrors the V1 DEFAULT_MOTIE_PROMPT in
data_capture_service.adapters.motie.motie_adapter — that prompt has historically
produced working FastAPI scrapers (e.g. the deployed purplebricks scraper). We
deliberately do not say "FastAPI scraper" in the opening line because the V1
"Build a scraper" wording is what's been working in production.
"""

from typing import Any, Dict, Optional

# Default field list — matches V1's DEFAULT_MOTIE_PROMPT. Field names use the
# user-facing labels Motie's agent will see; CANONICAL_TO_PROMPT_KEY in the
# motie_adapter does the reverse mapping for repair prompts.
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
    Prompt for an initial build. Matches V1's DEFAULT_MOTIE_PROMPT body verbatim
    so we ride the same agent behaviour that produced today's working scrapers,
    with the target URL prepended so the agent has a concrete page to reason
    against. benchmark_fields, when supplied, are AI-fetcher (e.g. Firecrawl)
    results that confirm specific fields exist on this URL.
    """
    sections = [
        f"Target URL: {url}",
        "",
        "Build a scraper for this property listing website. "
        "The scraper should accept a listing_url query parameter and extract "
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
    missing_critical_fields: Optional[Any] = None,
    benchmark_fields: Optional[Dict[str, Any]] = None,
    extra_context: Optional[str] = None,
) -> str:
    """
    Prompt for a repair session on an existing project.

    Emphasises that the agent has access to the prior code in the project and
    should fix it rather than rewrite from scratch. Matches V1's repair-prompt
    style (same field list, plain listing_url query param, no FastAPI mention).

    `missing_critical_fields` (P0 + P1) gets called out *before* the long
    list, because that's the diff that actually moves the score for the
    next build attempt.
    """
    sections = [
        "The deployed scraper for this property listing website is failing or "
        "returning errors.",
        "",
        f"Failing URL: {url}",
        f"Error: {failing_error}",
        "",
        "Please review the existing scraper code in this project, identify what "
        "is broken, and fix it so this URL extracts cleanly.",
        "",
        "The scraper should accept a listing_url query parameter and extract "
        "all property details from the page at that URL.",
    ]

    if missing_critical_fields:
        sections.append("")
        sections.append(
            "PRIORITY: the previous build did NOT capture these essential "
            f"fields, which the AI fetcher confirmed ARE on this page: "
            f"{list(missing_critical_fields)}. Fix extraction for these first."
        )

    sections.extend(
        [
            "",
            "Extract these fields and return them as a JSON object. If a detail "
            "isn't present on the page, put null as the value:",
            "",
            PROPERTY_FIELDS,
        ]
    )

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
