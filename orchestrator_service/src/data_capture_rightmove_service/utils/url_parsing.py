"""
Utility functions for parsing URLs and extracting useful information.
"""

import re
from typing import Optional, Tuple
from urllib.parse import urlparse

# Regex pattern for extracting property ID from Rightmove URLs
# Matches patterns like:
# - https://www.rightmove.co.uk/properties/154508327
# - https://www.rightmove.co.uk/properties/154508327#/?channel=RES_LET
RIGHTMOVE_PROPERTY_ID_PATTERN = r"rightmove\.co\.uk/properties/(\d+)"


def extract_rightmove_property_id(url: str) -> Optional[int]:
    """
    Extract the property ID from a Rightmove URL.
    
    Args:
        url: A Rightmove property URL
        
    Returns:
        int: The extracted property ID, or None if not found
        
    Examples:
        >>> extract_rightmove_property_id("https://www.rightmove.co.uk/properties/154508327#/?channel=RES_LET")
        154508327
        >>> extract_rightmove_property_id("https://www.rightmove.co.uk/properties/123456789")
        123456789
    """
    if not url:
        return None
    
    # Parse URL to validate it's a proper URL
    try:
        parsed_url = urlparse(url)
        if not parsed_url.netloc or "rightmove.co.uk" not in parsed_url.netloc.lower():
            return None
    except Exception:
        return None
        
    # Extract property ID using regex
    match = re.search(RIGHTMOVE_PROPERTY_ID_PATTERN, url)
    if match and match.group(1):
        try:
            return int(match.group(1))
        except ValueError:
            return None
            
    return None


def is_valid_rightmove_url(url: str) -> bool:
    """
    Check if a URL is a valid Rightmove property URL.
    
    Args:
        url: URL to check
        
    Returns:
        bool: True if the URL is a valid Rightmove property URL, False otherwise
    """
    if not url:
        return False
        
    # First validate it's a proper URL with rightmove.co.uk domain
    try:
        parsed_url = urlparse(url)
        if not parsed_url.netloc or "rightmove.co.uk" not in parsed_url.netloc.lower():
            return False
    except Exception:
        return False
    
    # Check if it has a property ID
    return extract_rightmove_property_id(url) is not None


def determine_rightmove_api_endpoints(url: str) -> Tuple[str, str]:
    """
    Determine which Rightmove API endpoints to use based on the URL structure.
    
    Args:
        url: A Rightmove property URL
        
    Returns:
        Tuple[str, str]: A tuple of (primary_endpoint, secondary_endpoint)
        Where primary is the preferred endpoint to try first
    """
    if not url:
        return ("properties_details", "property_for_sale")
    
    # Default choice
    primary = "properties_details"
    secondary = "property_for_sale"
    
    # If the URL contains keywords indicating it's a property for sale,
    # prioritize the property-for-sale endpoint
    url_lower = url.lower()
    if "property-for-sale" in url_lower or "for-sale" in url_lower:
        primary, secondary = secondary, primary
    
    return (primary, secondary)
