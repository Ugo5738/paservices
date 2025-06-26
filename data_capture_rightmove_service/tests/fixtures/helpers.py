"""
Helper functions and fixtures for testing the data_capture_rightmove_service.
"""
import uuid
import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.models.properties_details_v2 import (
    ApiPropertiesDetailsV2,
    ApiPropertiesDetailsV2Misinfo,
    ApiPropertiesDetailsV2Price,
    ApiPropertiesDetailsV2Status
)
from data_capture_rightmove_service.models.property_details import (
    ApiPropertyDetails,
    ApiPropertyDetailAddress,
    ApiPropertyDetailPrice,
    ApiPropertyDetailCustomer
)


@pytest.fixture
async def seed_properties_details_v2():
    """
    Helper fixture to seed a Rightmove properties details v2 record with optional related entities.
    """
    async def _seed_property(
        db_session: AsyncSession, 
        property_id: int = None, 
        with_relations: bool = True,
        price: int = None,
        bedrooms: int = None,
        property_type: str = None
    ) -> int:
        """
        Seed a test properties_details_v2 record.
        
        Args:
            db_session: The database session
            property_id: Optional property ID to use (BigInt)
            with_relations: Whether to create related records too
            price: Optional specific price to set
            bedrooms: Optional specific bedroom count
            property_type: Optional specific property type
            
        Returns:
            The ID of the created property
        """
        if property_id is None:
            property_id = random.randint(10000000, 99999999)
        
        if bedrooms is None:
            bedrooms = random.randint(1, 5)
            
        if property_type is None:
            property_type = random.choice([
                "FLAT", "TERRACED", "SEMI_DETACHED", "DETACHED", "BUNGALOW", "LAND"
            ])
            
        if price is None:
            price = random.randint(100000, 1000000)
        
        # Create main property record
        property_record = ApiPropertiesDetailsV2(
            id=property_id,
            transaction_type="SALE",
            bedrooms=bedrooms,
            property_type=property_type,
            summary=f"Test property with {bedrooms} bedrooms",
            address=f"{property_id} Test Street, Testville",
            super_id=uuid.uuid4()
        )
        db_session.add(property_record)
        await db_session.flush()
        
        if with_relations:
            # Add misinfo relation
            misinfo = ApiPropertiesDetailsV2Misinfo(
                api_property_id=property_id,
                branch_id=random.randint(1000, 9999),
                brand_plus=random.choice([True, False]),
                featured_property=random.choice([True, False]), 
                channel="BUY",
                super_id=uuid.uuid4()
            )
            db_session.add(misinfo)
            
            # Add price relation
            price_record = ApiPropertiesDetailsV2Price(
                api_property_id=property_id,
                amount=price,
                currency_code="GBP",
                frequency=None,
                qualifier=random.choice([
                    "Guide Price", "Offers Over", "Fixed Price", "From"
                ]),
                super_id=uuid.uuid4()
            )
            db_session.add(price_record)
            
            # Add status relation
            status = ApiPropertiesDetailsV2Status(
                api_property_id=property_id,
                display_status="FOR_SALE",
                published=True,
                can_display_photos=True,
                can_display_floorplans=True,
                super_id=uuid.uuid4()
            )
            db_session.add(status)
            
        await db_session.commit()
        return property_id
    
    return _seed_property


@pytest.fixture
async def seed_property_details():
    """
    Helper fixture to seed a Rightmove property details record with optional related entities.
    """
    async def _seed_property(
        db_session: AsyncSession, 
        property_id: int = None, 
        with_relations: bool = True,
        location: Dict[str, float] = None,
        features: List[str] = None
    ) -> int:
        """
        Seed a test property_details record.
        
        Args:
            db_session: The database session
            property_id: Optional property ID to use (BigInt)
            with_relations: Whether to create related records too
            location: Optional dict with latitude/longitude
            features: Optional list of property features
            
        Returns:
            The ID of the created property
        """
        if property_id is None:
            property_id = random.randint(10000000, 99999999)
            
        if features is None:
            features = ["Garden", "Parking", "Central Heating"]
            
        if location is None:
            # Default to central London area
            location = {
                "latitude": 51.5074 + (random.random() - 0.5) / 10,  # Add small random variation
                "longitude": -0.1278 + (random.random() - 0.5) / 10
            }
        
        # Create main property record
        property_record = ApiPropertyDetails(
            id=property_id,
            transaction_type="SALE",
            bedrooms=random.randint(1, 5),
            key_features=features,
            business_for_sale=False,
            commercial=False,
            super_id=uuid.uuid4()
        )
        db_session.add(property_record)
        await db_session.flush()
        
        if with_relations:
            # Add address
            address = ApiPropertyDetailAddress(
                api_property_detail_id=property_id,
                display_address=f"{random.randint(1, 999)} Test Road, Testington",
                country_code="GB",
                outcode=f"TE{random.randint(1, 20)}",
                incode=f"{random.randint(1, 9)}AB",
                super_id=uuid.uuid4()
            )
            db_session.add(address)
            
            # Add price record
            price = ApiPropertyDetailPrice(
                api_property_detail_id=property_id,
                currency_code="GBP",
                display_price=f"£{random.randint(100, 999)},000",
                super_id=uuid.uuid4()
            )
            db_session.add(price)
            
            # Add customer
            customer = ApiPropertyDetailCustomer(
                api_property_detail_id=property_id,
                branch_id=random.randint(1000, 9999),
                branch_name=f"Test Branch {random.randint(1, 50)}",
                company_name="Test Property Company Ltd",
                super_id=uuid.uuid4()
            )
            db_session.add(customer)
            
        await db_session.commit()
        return property_id
    
    return _seed_property


@pytest.fixture
def generate_property_data():
    """
    Helper to generate realistic property data for testing without database persistence.
    """
    def _generate_data(
        transaction_type: str = "SALE",
        property_type: str = None,
        bedrooms: int = None
    ) -> Dict[str, Any]:
        """
        Generate sample property data.
        
        Args:
            transaction_type: Type of transaction (SALE or RENT)
            property_type: Type of property
            bedrooms: Number of bedrooms
            
        Returns:
            Dict with property data
        """
        if property_type is None:
            property_type = random.choice([
                "FLAT", "TERRACED", "SEMI_DETACHED", "DETACHED", "BUNGALOW"
            ])
            
        if bedrooms is None:
            bedrooms = random.randint(1, 5)
            
        # Base property data
        town = random.choice(["London", "Manchester", "Birmingham", "Leeds", "Liverpool"])
        postcode = f"{random.choice(['SW', 'NW', 'SE', 'NE', 'W', 'E'])}{random.randint(1, 20)} {random.randint(1, 9)}AB"
        
        # Price based on property type and bedrooms
        base_price = {
            "FLAT": 200000,
            "TERRACED": 250000,
            "SEMI_DETACHED": 350000,
            "DETACHED": 450000,
            "BUNGALOW": 300000,
        }.get(property_type, 300000)
        
        # Add price per bedroom
        price = base_price + (bedrooms * 50000)
        
        # Add location randomization
        price = price + random.randint(-50000, 50000)
        
        # Generate property data
        property_data = {
            "id": random.randint(10000000, 99999999),
            "transaction_type": transaction_type,
            "property_type": property_type,
            "property_sub_type": f"{property_type}_HOUSE" if property_type != "FLAT" else "FLAT_APARTMENT",
            "bedrooms": bedrooms,
            "bathrooms": min(bedrooms, random.randint(1, 3)),
            "address": f"{random.randint(1, 999)} Test Street, {town}",
            "display_address": f"Test Street, {town}",
            "summary": f"A {'stunning' if random.random() > 0.5 else 'beautiful'} {bedrooms} bedroom {property_type.lower()}",
            "description": f"This {property_type.lower()} offers spacious accommodation with {bedrooms} bedrooms, located in a popular area of {town}.",
            "price": {
                "amount": price,
                "currency_code": "GBP",
                "display_price": f"£{price:,}",
                "qualifier": random.choice(["Guide Price", "Offers Over", "Fixed Price"])
            },
            "location": {
                "latitude": 51.5074 + (random.random() - 0.5),
                "longitude": -0.1278 + (random.random() - 0.5),
            },
            "postcode": postcode,
            "added_date": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
            "features": [
                "Gas Central Heating",
                "Double Glazing",
                f"{bedrooms} Bedrooms",
                "Garden" if random.random() > 0.3 else "Balcony",
                "Parking" if random.random() > 0.5 else "Garage"
            ]
        }
        
        return property_data
        
    return _generate_data
