"""
URL utility functions for domain extraction and normalization.
"""

from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """
    Extract the domain from a URL.

    Examples:
        "https://www.rightmove.co.uk/properties/123" -> "rightmove.co.uk"
        "https://www.zoopla.co.uk/for-sale/details/456/" -> "zoopla.co.uk"
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    # Strip www. prefix
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname.lower()


def normalize_url(url: str) -> str:
    """
    Normalize a URL for consistent comparison.
    Strips trailing slashes, fragments, and lowercases the scheme+host.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/") or "/"
    query = parsed.query

    normalized = f"{scheme}://{hostname}"
    if parsed.port and parsed.port not in (80, 443):
        normalized += f":{parsed.port}"
    normalized += path
    if query:
        normalized += f"?{query}"

    return normalized
