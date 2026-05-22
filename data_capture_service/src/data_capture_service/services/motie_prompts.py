"""
Motie agent prompt templates for build and repair sessions.

Centralizing the prompts here keeps them out of router code and makes them easy
to iterate on without touching control flow.

The wording mirrors the V1 DEFAULT_MOTIE_PROMPT in
data_capture_service.adapters.motie.motie_adapter — that prompt has historically
produced working FastAPI scrapers (e.g. the deployed purplebricks scraper). We
deliberately do not say "FastAPI scraper" in the opening line because the V1
"Build a scraper" wording is what's been working in production.

Runtime constraint (added 2026-05-22): the V2-era Motie agent sometimes
generates pipeline-style code that writes intermediate artifacts to
`/root/pipeline/artifacts/...`. The deployed environment (AWS Lambda / API
Gateway) has a read-only root filesystem, so those writes crash every request
with `Permission denied`. We now explicitly tell the agent the env is
stateless + read-only so it produces in-memory-only scrapers.
"""

# Runtime constraint section reused by both build_initial_prompt and
# build_repair_prompt — kept as a module-level constant so the wording stays
# identical across initial builds and repairs (otherwise the agent may "fix"
# the filesystem error in a repair by switching to a different writable path
# like /var/log, which also fails).
_DEPLOYMENT_ENV_CONSTRAINTS = (
    "Deployment environment constraints (very important — the deployed "
    "scraper WILL CRASH on every request if violated):\n"
    "- The deployed runtime is a READ-ONLY filesystem (AWS Lambda / API "
    "Gateway-style container). Your scraper code MUST NOT write any files to "
    "disk during a request. No caching to disk, no artifact directories, no "
    "`/root/pipeline/artifacts/...`, no `/var/...`, no logging to files.\n"
    "- The scraper must be STATELESS: receive the URL, fetch the page in "
    "memory, parse in memory, return JSON. Each request is independent — do "
    "not persist intermediate state between requests.\n"
    "- If you absolutely need scratch space, only `/tmp` is writable, but "
    "in-memory processing (e.g. `io.BytesIO`, BeautifulSoup on a string) is "
    "strongly preferred and matches the reference scrapers (openrent, "
    "connells, purplebricks) that work in production."
)

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
    Prompt for an initial build.

    Mirrors VERBATIM the hand-crafted prompt that produced a working,
    deployable primelocation scraper on 2026-05-20 via direct Motie API
    invocation (see /tmp/motie_build_test.sh from that session). That
    deployment hit POST /fetch with a property URL and returned real
    structured data — proving the chain-independent baseline.

    Previous prompt iterations (V1 "Build a scraper" wording + the
    listing_url query-param + 36-field PROPERTY_FIELDS reference) produced
    scrapers that either hung Motie indefinitely or deployed but wrote
    artifacts to a read-only filesystem (`/root/pipeline/artifacts/...`)
    and 500'd on every request. Both failure modes were caused by the
    prompt giving the Motie agent too much freedom in architecture
    choice. This verbatim copy of the known-working prompt removes that
    freedom: explicit "Python FastAPI scraper", explicit POST /fetch
    endpoint contract, focused field list with type hints.

    `benchmark_fields` (optional) — passed through as a hint about which
    fields the AI fetcher confirmed are on the page.
    `extra_context` (optional) — appended verbatim.
    """
    # Domain extraction (cheap inline — no urlparse import needed for one call)
    domain = url.split('://', 1)[-1].split('/', 1)[0]
    if domain.startswith('www.'):
        domain = domain[4:]

    prompt = (
        f"Build a Python FastAPI scraper that takes a {domain} property "
        "listing URL and returns a JSON object with these fields (use null "
        "when a field is not on the page):\n"
        "\n"
        '  - price: string with currency symbol (e.g. "£500,000" or "£1,200 pcm")\n'
        "  - bedrooms: integer\n"
        "  - bathrooms: integer\n"
        "  - full_address: full address string\n"
        "  - postcode: UK postcode\n"
        "  - property_type: flat | terraced | detached | semi-detached | etc.\n"
        '  - transaction_type: "for sale" | "to rent"\n'
        "  - description: full listing description text\n"
        "  - image_urls: array of full-resolution photo URLs\n"
        "  - floorplan_urls: array of floorplan image URLs\n"
        "  - estate_agent_name\n"
        "\n"
        f"Sample URL pattern: {url}\n"
        "\n"
        'The endpoint should be POST /fetch with body {"url": "..."} and '
        "return the JSON above."
    )

    if benchmark_fields:
        present = [k for k, v in benchmark_fields.items() if v]
        if present:
            prompt += (
                "\n\nReference data: an independent extractor confirmed these "
                f"fields ARE present on this URL: {present}. Your scraper must "
                "extract all of them."
            )

    if extra_context:
        prompt += "\n\n" + extra_context

    return prompt


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
    domain = url.split('://', 1)[-1].split('/', 1)[0]
    if domain.startswith('www.'):
        domain = domain[4:]

    sections = [
        f"The deployed Python FastAPI scraper for {domain} is failing or "
        "returning errors.",
        "",
        f"Failing URL: {url}",
        f"Error: {failing_error}",
        "",
        "Please review the existing scraper code in this project, identify what "
        "is broken, and fix it so this URL extracts cleanly.",
        "",
        'The endpoint must remain POST /fetch with body {"url": "..."}, '
        "returning a JSON object with these fields (use null when a field "
        "is not on the page):",
        "",
        '  - price: string with currency symbol (e.g. "£500,000" or "£1,200 pcm")',
        "  - bedrooms: integer",
        "  - bathrooms: integer",
        "  - full_address: full address string",
        "  - postcode: UK postcode",
        "  - property_type: flat | terraced | detached | semi-detached | etc.",
        '  - transaction_type: "for sale" | "to rent"',
        "  - description: full listing description text",
        "  - image_urls: array of full-resolution photo URLs",
        "  - floorplan_urls: array of floorplan image URLs",
        "  - estate_agent_name",
    ]

    if missing_critical_fields:
        sections.append("")
        sections.append(
            "PRIORITY: the previous build did NOT capture these essential "
            f"fields, which the AI fetcher confirmed ARE on this page: "
            f"{list(missing_critical_fields)}. Fix extraction for these first."
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
