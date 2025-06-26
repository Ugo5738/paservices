#!/usr/bin/env python3
"""
Database verification script for Rightmove property data.
This script queries the database for a specific property ID and displays all related data.

Usage:
    python scripts/verify_property_data.py [property_id]
    
If property_id is not provided, the script will list the latest 10 properties.
"""

import argparse
import asyncio
import os
import sys
from typing import Dict, List, Optional, Union

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from tabulate import tabulate

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_capture_rightmove_service.config import settings
from data_capture_rightmove_service.models.properties_details import (
    ApiPropertiesDetailsV2,
    ApiPropertiesDetailsV2Branch,
    ApiPropertiesDetailsV2Floorplan,
    ApiPropertiesDetailsV2Location,
    ApiPropertiesDetailsV2Photo,
    ApiPropertiesDetailsV2Price,
)
from data_capture_rightmove_service.models.property_details import (
    ApiPropertyDetails,
    ApiPropertyDetailCustomer,
    ApiPropertyDetailFloorplan,
    ApiPropertyDetailImage,
    ApiPropertyDetailPrice,
)


class DataVerifier:
    """Database verification tool for Rightmove property data."""
    
    def __init__(self):
        """Initialize the database connection."""
        self.engine = create_async_engine(settings.DATABASE_URL)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def list_recent_properties(self, limit: int = 10) -> None:
        """List the most recent properties stored in the database."""
        print(f"📋 Listing the {limit} most recent properties...\n")
        
        async with self.async_session() as session:
            # Get recent properties from properties_details_v2
            result = await session.execute(
                select(ApiPropertiesDetailsV2)
                .order_by(ApiPropertiesDetailsV2.created_at.desc())
                .limit(limit)
            )
            properties_details = result.scalars().all()
            
            # Get recent properties from property_details
            result = await session.execute(
                select(ApiPropertyDetails)
                .order_by(ApiPropertyDetails.created_at.desc())
                .limit(limit)
            )
            property_details = result.scalars().all()
            
            # Combine and deduplicate by property_id
            all_properties = {}
            
            for prop in properties_details:
                all_properties[prop.id] = {
                    "property_id": prop.id,
                    "super_id": prop.super_id,
                    "created_at": prop.created_at,
                    "source": "properties_details",
                    "bedrooms": prop.bedrooms,
                    "address": prop.address,
                }
            
            for prop in property_details:
                if prop.property_id not in all_properties:
                    all_properties[prop.property_id] = {
                        "property_id": prop.property_id,
                        "super_id": prop.super_id,
                        "created_at": prop.created_at,
                        "source": "property_details",
                        "bedrooms": prop.bedrooms,
                        "address": prop.display_address,
                    }
                else:
                    # Already have this property from properties_details, mark as both
                    all_properties[prop.property_id]["source"] = "both"
            
            # Convert to list and sort by created_at
            properties_list = list(all_properties.values())
            properties_list.sort(key=lambda x: x["created_at"], reverse=True)
            
            # Display as table
            table_data = [
                [
                    p["property_id"],
                    p["super_id"],
                    p["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    p["source"],
                    p.get("bedrooms", "N/A"),
                    p.get("address", "N/A")[:50],  # Truncate long addresses
                ]
                for p in properties_list[:limit]
            ]
            
            headers = ["Property ID", "Super ID", "Created At", "Source", "Bedrooms", "Address"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print("\nUse a property ID from this list with this script to see full details.")
    
    async def verify_property(self, property_id: int) -> None:
        """Verify and display all data for a specific property ID."""
        print(f"🔍 Verifying property with ID: {property_id}\n")
        
        async with self.async_session() as session:
            await self._verify_properties_details(session, property_id)
            await self._verify_property_details(session, property_id)
    
    async def _verify_properties_details(self, session: AsyncSession, property_id: int) -> None:
        """Verify data in the properties_details_v2 tables."""
        print("📊 PROPERTIES_DETAILS_V2 DATA")
        print("=" * 80)
        
        # Check main record
        result = await session.execute(
            select(ApiPropertiesDetailsV2).where(ApiPropertiesDetailsV2.id == property_id)
        )
        main_record = result.scalar_one_or_none()
        
        if not main_record:
            print("❌ No record found in ApiPropertiesDetailsV2")
            return
        
        print(f"✅ Main record found (created: {main_record.created_at})")
        print(f"  - Super ID: {main_record.super_id}")
        print(f"  - Transaction Type: {main_record.transaction_type}")
        print(f"  - Channel: {main_record.channel}")
        print(f"  - Bedrooms: {main_record.bedrooms}")
        print(f"  - Bathrooms: {main_record.bathrooms}")
        print(f"  - Address: {main_record.address}")
        print(f"  - Property URL: {main_record.property_url}")
        
        if main_record.key_features:
            print("\n🔑 Key Features:")
            for feature in main_record.key_features:
                print(f"  - {feature}")
        
        # Check branch info
        result = await session.execute(
            select(ApiPropertiesDetailsV2Branch).where(ApiPropertiesDetailsV2Branch.api_property_id == property_id)
        )
        branch = result.scalar_one_or_none()
        
        print("\n🏢 Branch Information:")
        if branch:
            print(f"  - Branch ID: {branch.branch_id}")
            print(f"  - Name: {branch.name}")
            print(f"  - Company: {branch.company_name}")
            print(f"  - Address: {branch.address}")
        else:
            print("  ❌ No branch information found")
        
        # Check price info
        result = await session.execute(
            select(ApiPropertiesDetailsV2Price).where(ApiPropertiesDetailsV2Price.api_property_id == property_id)
        )
        price = result.scalar_one_or_none()
        
        print("\n💰 Price Information:")
        if price:
            print(f"  - Primary Price: {price.primary_price}")
            print(f"  - Secondary Price: {price.secondary_price}")
        else:
            print("  ❌ No price information found")
        
        # Check location info
        result = await session.execute(
            select(ApiPropertiesDetailsV2Location).where(ApiPropertiesDetailsV2Location.api_property_id == property_id)
        )
        location = result.scalar_one_or_none()
        
        print("\n📍 Location Information:")
        if location:
            print(f"  - Latitude: {location.latitude}")
            print(f"  - Longitude: {location.longitude}")
        else:
            print("  ❌ No location information found")
        
        # Check photos
        result = await session.execute(
            select(func.count()).select_from(ApiPropertiesDetailsV2Photo).where(
                ApiPropertiesDetailsV2Photo.api_property_id == property_id
            )
        )
        photo_count = result.scalar_one()
        
        print(f"\n📸 Photos: {photo_count}")
        if photo_count > 0:
            result = await session.execute(
                select(ApiPropertiesDetailsV2Photo).where(
                    ApiPropertiesDetailsV2Photo.api_property_id == property_id
                ).limit(3)
            )
            photos = result.scalars().all()
            for i, photo in enumerate(photos):
                print(f"  - Photo {i+1}: {photo.caption}")
                print(f"    URL: {photo.url}")
            
            if photo_count > 3:
                print(f"    ... and {photo_count - 3} more photos")
        
        # Check floorplans
        result = await session.execute(
            select(func.count()).select_from(ApiPropertiesDetailsV2Floorplan).where(
                ApiPropertiesDetailsV2Floorplan.api_property_id == property_id
            )
        )
        floorplan_count = result.scalar_one()
        
        print(f"\n📝 Floorplans: {floorplan_count}")
        if floorplan_count > 0:
            result = await session.execute(
                select(ApiPropertiesDetailsV2Floorplan).where(
                    ApiPropertiesDetailsV2Floorplan.api_property_id == property_id
                )
            )
            floorplans = result.scalars().all()
            for i, floorplan in enumerate(floorplans):
                print(f"  - Floorplan {i+1}: {floorplan.url}")
    
    async def _verify_property_details(self, session: AsyncSession, property_id: int) -> None:
        """Verify data in the property_details tables."""
        print("\n\n📊 PROPERTY_DETAILS DATA")
        print("=" * 80)
        
        # Check main record
        result = await session.execute(
            select(ApiPropertyDetails).where(ApiPropertyDetails.property_id == property_id)
        )
        main_record = result.scalar_one_or_none()
        
        if not main_record:
            print("❌ No record found in ApiPropertyDetails")
            return
        
        db_id = main_record.id
        
        print(f"✅ Main record found (created: {main_record.created_at})")
        print(f"  - Super ID: {main_record.super_id}")
        print(f"  - Property Type: {main_record.property_type}")
        print(f"  - Property Subtype: {main_record.property_subtype}")
        print(f"  - Bedrooms: {main_record.bedrooms}")
        print(f"  - Bathrooms: {main_record.bathrooms}")
        print(f"  - Display Address: {main_record.display_address}")
        print(f"  - Summary: {main_record.summary}")
        print(f"  - Property URL: {main_record.property_url}")
        
        if main_record.features:
            print("\n🔑 Features:")
            for feature in main_record.features:
                print(f"  - {feature}")
        
        # Check price info
        result = await session.execute(
            select(ApiPropertyDetailPrice).where(ApiPropertyDetailPrice.api_property_detail_id == db_id)
        )
        price = result.scalar_one_or_none()
        
        print("\n💰 Price Information:")
        if price:
            print(f"  - Display Price: {price.display_price}")
            print(f"  - Price Qualifier: {price.price_qualifier}")
            print(f"  - Currency Code: {price.currency_code}")
        else:
            print("  ❌ No price information found")
        
        # Check customer info
        result = await session.execute(
            select(ApiPropertyDetailCustomer).where(ApiPropertyDetailCustomer.api_property_detail_id == db_id)
        )
        customer = result.scalar_one_or_none()
        
        print("\n🏢 Customer Information:")
        if customer:
            print(f"  - Branch ID: {customer.branch_id}")
            print(f"  - Branch Name: {customer.branch_name}")
            print(f"  - Company Name: {customer.company_name}")
        else:
            print("  ❌ No customer information found")
        
        # Check images
        result = await session.execute(
            select(func.count()).select_from(ApiPropertyDetailImage).where(
                ApiPropertyDetailImage.api_property_detail_id == db_id
            )
        )
        image_count = result.scalar_one()
        
        print(f"\n📸 Images: {image_count}")
        if image_count > 0:
            result = await session.execute(
                select(ApiPropertyDetailImage).where(
                    ApiPropertyDetailImage.api_property_detail_id == db_id
                ).limit(3)
            )
            images = result.scalars().all()
            for i, image in enumerate(images):
                print(f"  - Image {i+1}: {image.caption}")
                print(f"    URL: {image.url}")
            
            if image_count > 3:
                print(f"    ... and {image_count - 3} more images")
        
        # Check floorplans
        result = await session.execute(
            select(func.count()).select_from(ApiPropertyDetailFloorplan).where(
                ApiPropertyDetailFloorplan.api_property_detail_id == db_id
            )
        )
        floorplan_count = result.scalar_one()
        
        print(f"\n📝 Floorplans: {floorplan_count}")
        if floorplan_count > 0:
            result = await session.execute(
                select(ApiPropertyDetailFloorplan).where(
                    ApiPropertyDetailFloorplan.api_property_detail_id == db_id
                )
            )
            floorplans = result.scalars().all()
            for i, floorplan in enumerate(floorplans):
                print(f"  - Floorplan {i+1}: {floorplan.caption if floorplan.caption else 'No caption'}")
                print(f"    URL: {floorplan.url}")
    
    async def close(self) -> None:
        """Close the database connection."""
        await self.engine.dispose()


async def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Verify Rightmove property data in the database")
    parser.add_argument("property_id", nargs="?", type=int, help="Property ID to verify")
    args = parser.parse_args()
    
    verifier = DataVerifier()
    
    try:
        if args.property_id:
            await verifier.verify_property(args.property_id)
        else:
            await verifier.list_recent_properties()
    finally:
        await verifier.close()


if __name__ == "__main__":
    asyncio.run(main())
