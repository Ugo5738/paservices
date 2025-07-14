"""
Rightmove API Client for fetching property data from RapidAPI.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

from data_capture_rightmove_service.config import settings

logger = logging.getLogger(__name__)


class RightmoveApiClient:
    """
    Client for fetching property data from the Rightmove API via RapidAPI.
    Handles rate limiting, error handling, and response parsing.
    """

    def __init__(self, api_key: str = None, api_host: str = None):
        """
        Initialize the Rightmove API Client.

        Args:
            api_key: RapidAPI key, defaults to the value in settings
            api_host: RapidAPI host, defaults to the value in settings
        """
        # self.api_key = api_key or settings.RAPID_API_KEY
        self.api_key = "f846d19a60msh2784c2ba0508745p1f0be3jsn2676a9a367f6"
        self.api_host = api_host or settings.RAPID_API_HOST
        self.base_url = f"https://{self.api_host}"

        # Log the API key being used (last 6 chars for security)
        masked_key = "*****" + self.api_key[-6:] if self.api_key else "None"
        logger.info(
            f"RightmoveApiClient initialized with API key ending in: {masked_key}"
        )

        # Default headers for all requests
        self._default_headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 1,
    ) -> Dict[str, Any]:
        """
        Make a request to the Rightmove API with appropriate headers and error handling.

        Args:
            method: HTTP method to use (GET, POST, etc.)
            endpoint: API endpoint to call
            params: Query parameters to include
            max_retries: Maximum number of retries on rate limit errors

        Returns:
            Dict[str, Any]: API response data

        Raises:
            HTTPException: If the API request fails
        """
        url = f"{self.base_url}{endpoint}"
        retries = 0

        while retries <= max_retries:
            try:
                async with httpx.AsyncClient() as client:
                    if method.upper() == "GET":
                        response = await client.get(
                            url,
                            params=params,
                            headers=self._default_headers,
                            timeout=30.0,  # Longer timeout for property data
                        )
                    elif method.upper() == "POST":
                        response = await client.post(
                            url,
                            json=params,
                            headers=self._default_headers,
                            timeout=30.0,
                        )
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    # Handle rate limiting
                    if response.status_code == 429:
                        retries += 1
                        # Get reset time from headers if available
                        reset_seconds = response.headers.get(
                            "X-RateLimit-Requests-Reset"
                        )
                        if reset_seconds and reset_seconds.isdigit():
                            wait_time = min(int(reset_seconds) / 1000 + 1, 10)
                        else:
                            # Default exponential backoff with jitter
                            wait_time = min(2**retries + 0.5, 10)

                        if retries > max_retries:
                            logger.error("Rate limit exceeded and max retries reached")
                            raise HTTPException(
                                status_code=429,
                                detail="Rate limit exceeded from RapidAPI Rightmove API",
                            )
                        logger.warning(
                            f"Rate limit hit, waiting {wait_time}s before retry {retries}/{max_retries}..."
                        )
                        # Always add a delay between requests - matching the working script
                        await asyncio.sleep(wait_time)
                        continue

                    # Add a small delay between successful requests to prevent rate limiting
                    # Similar to the time.sleep(0.5) in your working script
                    await asyncio.sleep(0.5)

                    # Handle other errors
                    response.raise_for_status()

                    # Parse the response JSON
                    response_data = response.json()

                    # Log the response structure for debugging
                    logger.debug(f"API Response URL: {url}")
                    logger.debug(f"API Response Status: {response.status_code}")
                    logger.debug(
                        f"API Response Structure - Top-level keys: {list(response_data.keys())}"
                    )

                    # Log nested data structure if present
                    if "data" in response_data and isinstance(
                        response_data["data"], dict
                    ):
                        logger.debug(
                            f"API Response Nested data keys: {list(response_data['data'].keys())}"
                        )

                        # Look for ID fields in the nested data
                        id_fields = ["id", "propertyId", "property_id"]
                        for field in id_fields:
                            if field in response_data["data"]:
                                logger.debug(
                                    f"Found ID field '{field}' in data: {response_data['data'][field]}"
                                )

                    return response_data

            except httpx.HTTPError as e:
                logger.error(f"HTTP error when calling Rightmove API: {str(e)}")
                if hasattr(e, "response") and e.response is not None:
                    status_code = e.response.status_code
                    try:
                        error_detail = e.response.json()
                        detail = f"Rightmove API error: {error_detail}"
                    except Exception:
                        detail = f"Rightmove API error: {str(e)}"
                else:
                    status_code = 503
                    detail = f"Rightmove API service unavailable: {str(e)}"

                raise HTTPException(status_code=status_code, detail=detail)

            except Exception as e:
                logger.error(f"Unexpected error when calling Rightmove API: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Unexpected error when calling Rightmove API: {str(e)}",
                )

    async def get_property_details(self, property_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific property using the properties/details endpoint.

        Args:
            property_id: The Rightmove property ID

        Returns:
            Dict[str, Any]: Property details

        Raises:
            HTTPException: If the API request fails
        """
        endpoint = settings.RIGHTMOVE_API_PROPERTIES_DETAILS_ENDPOINT
        params = {"identifier": property_id}

        logger.info(f"Fetching property details for ID: {property_id}")
        return await self._make_request("GET", endpoint, params, max_retries=2)

    async def get_property_for_sale_details(self, property_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a property for sale using the correct endpoint.

        Args:
            property_id: The Rightmove property ID

        Returns:
            Dict[str, Any]: Property details

        Raises:
            HTTPException: If the API request fails
        """
        # The correct endpoint format is /buy/property-for-sale/detail with 'id' parameter
        endpoint = f"{settings.RIGHTMOVE_API_PROPERTY_FOR_SALE_ENDPOINT}/detail"
        params = {"id": property_id}

        logger.info(
            f"Fetching property-for-sale details for ID: {property_id} using endpoint {endpoint}"
        )
        return await self._make_request("GET", endpoint, params, max_retries=2)

    async def search_properties_for_sale(
        self,
        location_identifier: str,
        page_number: int = 1,
        sort_type: Optional[str] = "HighestPrice",
        radius_from_location: Optional[float] = 1.0,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_bedrooms: Optional[int] = None,
        max_bedrooms: Optional[int] = None,
        property_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search for properties for sale based on criteria.

        Args:
            location_identifier: The location to search in (e.g., "REGION^87490" for London).
            min_price: Minimum price
            max_price: Maximum price
            min_bedrooms: Minimum number of bedrooms
            max_bedrooms: Maximum number of bedrooms
            property_type: Type of property (e.g., "FLAT", "HOUSE")
            radius_from_location: Search radius in miles.
            page_number: Page number for pagination
            sort_type: Sort type for the search results

        Returns:
            Dict[str, Any]: Search results

        Raises:
            HTTPException: If the API request fails
        """
        endpoint = f"{settings.RIGHTMOVE_API_PROPERTY_FOR_SALE_ENDPOINT}"

        # Build query parameters - exact match with working script
        params = {
            "identifier": location_identifier,
            "page": str(page_number),
            "sort_by": sort_type,
            "search_radius": str(radius_from_location) if radius_from_location is not None else "1.0",
        }

        if min_price is not None:
            params["minPrice"] = min_price

        if max_price is not None:
            params["maxPrice"] = max_price

        if min_bedrooms is not None:
            params["minBedrooms"] = min_bedrooms

        if max_bedrooms is not None:
            params["maxBedrooms"] = max_bedrooms

        if property_type is not None:
            params["propertyType"] = property_type

        logger.info(f"Searching properties for sale with criteria: {params}")
        return await self._make_request("GET", endpoint, params, max_retries=2)


# Create a global instance of the Rightmove API client
rightmove_api_client = RightmoveApiClient()
