#!/usr/bin/env python3
"""
Integration test script for testing the property data capture service with real Rightmove URLs.
This script sends requests to the service API and verifies the responses and database records.

Usage:
    python scripts/integration_test.py

Environment variables:
    DATA_CAPTURE_RIGHTMOVE_SERVICE_API_URL: The base URL for the service API (default: http://localhost:8000)
    RIGHTMOVE_TEST_URL: A test Rightmove property URL to use
"""

import asyncio
import json
import os
import sys
import uuid
from typing import Dict, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_capture_rightmove_service.config import settings
from data_capture_rightmove_service.models.properties_details import (
    ApiPropertiesDetailsV2,
)
from data_capture_rightmove_service.models.property_details import ApiPropertyDetails
from data_capture_rightmove_service.utils.url_parsing import (
    extract_rightmove_property_id,
)

# Configuration
API_URL = os.environ.get(
    "DATA_CAPTURE_RIGHTMOVE_SERVICE_API_URL", "http://localhost:8003"
)
TEST_URL = os.environ.get(
    "RIGHTMOVE_TEST_URL", "https://www.rightmove.co.uk/properties/154508327"
)


class IntegrationTester:
    """Integration tester for the property data capture service."""

    def __init__(self):
        """Initialize the tester."""
        self.client = httpx.AsyncClient(base_url=API_URL, timeout=60.0)
        self.engine = create_async_engine(settings.DATABASE_URL)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self.property_id = None
        self.super_ids = []

    async def setup(self):
        """Set up the test environment."""
        print(f"🔵 Setting up integration test for {API_URL}")
        print(f"🔵 Using test URL: {TEST_URL}")

        # Extract property ID from the URL for validation
        self.property_id = extract_rightmove_property_id(TEST_URL)
        if not self.property_id:
            print("❌ Failed to extract property ID from test URL")
            sys.exit(1)

        print(f"🔵 Extracted property ID: {self.property_id}")

    async def validate_url(self) -> bool:
        """Test the URL validation endpoint."""
        print("\n🔍 Testing URL validation endpoint...")

        try:
            response = await self.client.get(
                f"/properties/validate-url", params={"url": TEST_URL}
            )

            if response.status_code != 200:
                print(f"❌ URL validation failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return False

            data = response.json()
            print(f"✅ URL validation successful: {json.dumps(data, indent=2)}")

            if not data.get("valid"):
                print("❌ URL was reported as invalid")
                return False

            if data.get("property_id") != self.property_id:
                print(
                    f"❌ Property ID mismatch: {data.get('property_id')} vs {self.property_id}"
                )
                return False

            return True

        except Exception as e:
            print(f"❌ Exception during URL validation: {e}")
            return False

    async def fetch_combined_data(self) -> bool:
        """Test the combined data fetch endpoint."""
        print("\n🔍 Testing combined data fetch endpoint...")

        try:
            # Generate a test super_id
            test_super_id = uuid.uuid4()

            response = await self.client.post(
                "/properties/fetch/combined",
                json={
                    "property_url": TEST_URL,
                    "super_id": str(test_super_id),
                    "description": "Integration test",
                },
            )

            if response.status_code != 200:
                print(f"❌ Combined fetch failed with status {response.status_code}")
                print(f"Response: {response.text}")
                return False

            data = response.json()
            print(f"✅ Combined fetch successful")
            print(f"Results: {len(data.get('results', []))} API endpoints processed")

            # Store super_ids for database verification
            self.super_ids = [
                uuid.UUID(result["super_id"])
                for result in data.get("results", [])
                if result.get("super_id")
            ]

            # Verify both API endpoints were called and data was stored
            if len(data.get("results", [])) != 2:
                print(f"❌ Expected 2 API results, got {len(data.get('results', []))}")
                return False

            # Check all results for success
            all_success = all(
                result.get("stored", False) for result in data.get("results", [])
            )
            if not all_success:
                print("❌ Not all data was stored successfully")
                for result in data.get("results", []):
                    if not result.get("stored"):
                        print(
                            f"  - {result.get('api_endpoint')}: {result.get('message')}"
                        )
                return False

            print(f"✅ All data stored successfully")
            return True

        except Exception as e:
            print(f"❌ Exception during combined fetch: {e}")
            return False

    async def verify_database_records(self) -> bool:
        """Verify that data was properly stored in the database."""
        print("\n🔍 Verifying database records...")

        if not self.property_id:
            print("❌ Missing property ID for verification")
            return False

        if not self.super_ids:
            print("❌ Missing super IDs for verification")
            return False

        try:
            async with self.async_session() as session:
                # Check properties_details table
                result = await session.execute(
                    select(ApiPropertiesDetailsV2).where(
                        ApiPropertiesDetailsV2.id == self.property_id
                    )
                )
                properties_details = result.scalar_one_or_none()

                if not properties_details:
                    print(
                        f"❌ No record found in ApiPropertiesDetailsV2 for ID {self.property_id}"
                    )
                    return False

                print(f"✅ Found properties_details record for ID {self.property_id}")

                # Check property_details table
                result = await session.execute(
                    select(ApiPropertyDetails).where(
                        ApiPropertyDetails.property_id == self.property_id
                    )
                )
                property_details = result.scalar_one_or_none()

                if not property_details:
                    print(
                        f"❌ No record found in ApiPropertyDetails for ID {self.property_id}"
                    )
                    return False

                print(f"✅ Found property_details record for ID {self.property_id}")

                # Verify that all necessary data was stored
                await self._verify_data_completeness(session, self.property_id)

                return True

        except Exception as e:
            print(f"❌ Exception during database verification: {e}")
            return False

    async def _verify_data_completeness(
        self, session: AsyncSession, property_id: int
    ) -> None:
        """Verify that all necessary data fields are populated in the database."""
        try:
            # Verify properties_details record has related entities
            # Check for branch info
            result = await session.execute(
                "SELECT COUNT(*) FROM properties_details_v2_branch WHERE api_property_id = :pid",
                {"pid": property_id},
            )
            branch_count = result.scalar_one()
            print(f"  - Branch records: {branch_count}")

            # Check for price info
            result = await session.execute(
                "SELECT COUNT(*) FROM properties_details_v2_price WHERE api_property_id = :pid",
                {"pid": property_id},
            )
            price_count = result.scalar_one()
            print(f"  - Price records: {price_count}")

            # Check for location info
            result = await session.execute(
                "SELECT COUNT(*) FROM properties_details_v2_location WHERE api_property_id = :pid",
                {"pid": property_id},
            )
            location_count = result.scalar_one()
            print(f"  - Location records: {location_count}")

            # Check for photos
            result = await session.execute(
                "SELECT COUNT(*) FROM properties_details_v2_photo WHERE api_property_id = :pid",
                {"pid": property_id},
            )
            photo_count = result.scalar_one()
            print(f"  - Photo records: {photo_count}")

            # Check for floorplans
            result = await session.execute(
                "SELECT COUNT(*) FROM properties_details_v2_floorplan WHERE api_property_id = :pid",
                {"pid": property_id},
            )
            floorplan_count = result.scalar_one()
            print(f"  - Floorplan records: {floorplan_count}")

            # Verify property_details record has related entities
            # Check for customer info
            result = await session.execute(
                "SELECT COUNT(*) FROM property_detail_customer WHERE api_property_detail_id = "
                "(SELECT id FROM property_details WHERE property_id = :pid)",
                {"pid": property_id},
            )
            customer_count = result.scalar_one()
            print(f"  - Customer records: {customer_count}")

            # Check for images
            result = await session.execute(
                "SELECT COUNT(*) FROM property_detail_image WHERE api_property_detail_id = "
                "(SELECT id FROM property_details WHERE property_id = :pid)",
                {"pid": property_id},
            )
            image_count = result.scalar_one()
            print(f"  - Image records: {image_count}")

            # Check for floorplans
            result = await session.execute(
                "SELECT COUNT(*) FROM property_detail_floorplan WHERE api_property_detail_id = "
                "(SELECT id FROM property_details WHERE property_id = :pid)",
                {"pid": property_id},
            )
            detail_floorplan_count = result.scalar_one()
            print(f"  - Detail floorplan records: {detail_floorplan_count}")

        except Exception as e:
            print(f"❌ Exception during data completeness check: {e}")

    async def run(self) -> None:
        """Run the integration tests."""
        try:
            await self.setup()

            # Step 1: Validate URL endpoint
            url_valid = await self.validate_url()
            if not url_valid:
                print("❌ URL validation test failed")
                return

            # Step 2: Test combined fetch endpoint
            fetch_success = await self.fetch_combined_data()
            if not fetch_success:
                print("❌ Combined fetch test failed")
                return

            # Step 3: Verify database records
            db_verified = await self.verify_database_records()
            if not db_verified:
                print("❌ Database verification failed")
                return

            print("\n✅ All tests passed successfully!")

        except Exception as e:
            print(f"❌ Integration test failed with unexpected error: {e}")
        finally:
            await self.client.aclose()
            await self.engine.dispose()


if __name__ == "__main__":
    tester = IntegrationTester()
    asyncio.run(tester.run())
