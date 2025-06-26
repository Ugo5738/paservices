"""
Unit tests for the properties_details_v2 SQLAlchemy models.
Tests database interactions and model relationships using the test database.
"""
import uuid
import pytest
import logging
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.models.properties_details_v2 import (
    ApiPropertiesDetailsV2,
    ApiPropertiesDetailsV2Misinfo,
    ApiPropertiesDetailsV2Status,
    ApiPropertiesDetailsV2StampDuty,
    ApiPropertiesDetailsV2Features,
    ApiPropertiesDetailsV2Branch,
    ApiPropertiesDetailsV2Price
)

# Set up logger
logger = logging.getLogger(__name__)


class TestPropertiesDetailsV2Models:
    """Test suite for properties_details_v2 models and their relationships."""
    
    @pytest.mark.asyncio
    async def test_create_main_property_model(self, db_session):
        """Test creating a property record with basic fields."""
        # Arrange - Create property data
        property_id = 12345678
        test_property = ApiPropertiesDetailsV2(
            id=property_id,
            transaction_type="SALE",
            bedrooms=3,
            address="123 Test Street, Testville",
            summary="A test property with 3 bedrooms",
            display_address="Test Street, Testville",
            property_type="TERRACED",
            property_sub_type="TERRACED_HOUSE",
            bathrooms=2,
            view_count=150
        )
        
        # Act - Save to database
        db_session.add(test_property)
        await db_session.flush()
        
        # Generate a super_id value
        test_property.super_id = uuid.uuid4()
        await db_session.commit()
        
        # Assert - Verify record was saved properly
        result = await db_session.execute(
            select(ApiPropertiesDetailsV2).where(ApiPropertiesDetailsV2.id == property_id)
        )
        saved_property = result.scalars().first()
        
        # Check field values
        assert saved_property is not None
        assert saved_property.id == property_id
        assert saved_property.transaction_type == "SALE"
        assert saved_property.bedrooms == 3
        assert saved_property.address == "123 Test Street, Testville"
        assert saved_property.summary == "A test property with 3 bedrooms"
        assert saved_property.property_type == "TERRACED"
        assert saved_property.property_sub_type == "TERRACED_HOUSE"
        assert saved_property.super_id is not None

    @pytest.mark.asyncio
    async def test_create_property_with_relationships(self, db_session):
        """Test creating a property with related records."""
        # Arrange - Create property record with ID
        property_id = 23456789
        test_property = ApiPropertiesDetailsV2(
            id=property_id,
            transaction_type="SALE",
            bedrooms=3,
            address="456 Related Property, Testborough"
        )
        
        # Add property and flush to generate ID
        db_session.add(test_property)
        await db_session.flush()
        
        # Create related records
        misinfo = ApiPropertiesDetailsV2Misinfo(
            api_property_id=property_id,
            branch_id=9876,
            brand_plus=True,
            featured_property=True,
            channel="BUY",
            premium_display=False
        )
        
        status = ApiPropertiesDetailsV2Status(
            api_property_id=property_id,
            display_status="FOR_SALE",
            can_display_floorplans=True,
            can_display_photos=True,
            published=True
        )
        
        price = ApiPropertiesDetailsV2Price(
            api_property_id=property_id,
            amount=350000,
            currency_code="GBP",
            qualifier="Guide Price"
        )
        
        # Add related records to session
        db_session.add_all([misinfo, status, price])
        await db_session.commit()
        
        # Act - Query the property with related data
        result = await db_session.execute(
            select(ApiPropertiesDetailsV2).where(ApiPropertiesDetailsV2.id == property_id)
        )
        saved_property = result.scalars().first()
        
        # Assert - Check relationships loaded correctly
        assert saved_property is not None
        
        # Check each relationship
        assert saved_property.misinfo is not None
        assert saved_property.misinfo.branch_id == 9876
        assert saved_property.misinfo.brand_plus is True
        
        assert saved_property.status is not None
        assert saved_property.status.display_status == "FOR_SALE"
        assert saved_property.status.published is True
        
        assert saved_property.price is not None
        assert saved_property.price.amount == 350000
        assert saved_property.price.currency_code == "GBP"
        
    @pytest.mark.asyncio
    async def test_cascade_delete(self, db_session):
        """Test cascade delete behavior between property and related tables."""
        # Arrange - Create property with related records
        property_id = 34567890
        
        # Create main property
        test_property = ApiPropertiesDetailsV2(
            id=property_id,
            transaction_type="SALE",
            bedrooms=2,
            address="789 Cascade Test Lane, Testford"
        )
        
        # Add property and flush to generate ID
        db_session.add(test_property)
        await db_session.flush()
        
        # Create related records
        misinfo = ApiPropertiesDetailsV2Misinfo(
            api_property_id=property_id,
            branch_id=5432,
            channel="BUY"
        )
        
        branch = ApiPropertiesDetailsV2Branch(
            api_property_id=property_id,
            branch_id=5432,
            branch_name="Test Branch",
            company_name="Test Property Company"
        )
        
        # Add related records to session
        db_session.add_all([misinfo, branch])
        await db_session.commit()
        
        # Act - Delete the main property record
        await db_session.execute(
            select(ApiPropertiesDetailsV2).where(ApiPropertiesDetailsV2.id == property_id)
        )
        property_to_delete = (await db_session.execute(
            select(ApiPropertiesDetailsV2).where(ApiPropertiesDetailsV2.id == property_id)
        )).scalars().first()
        
        await db_session.delete(property_to_delete)
        await db_session.commit()
        
        # Assert - Verify cascade delete worked
        # Check main property is gone
        property_check = (await db_session.execute(
            select(ApiPropertiesDetailsV2).where(ApiPropertiesDetailsV2.id == property_id)
        )).scalars().first()
        assert property_check is None
        
        # Check related records are gone
        misinfo_check = (await db_session.execute(
            select(ApiPropertiesDetailsV2Misinfo).where(ApiPropertiesDetailsV2Misinfo.api_property_id == property_id)
        )).scalars().first()
        assert misinfo_check is None
        
        branch_check = (await db_session.execute(
            select(ApiPropertiesDetailsV2Branch).where(ApiPropertiesDetailsV2Branch.api_property_id == property_id)
        )).scalars().first()
        assert branch_check is None

    @pytest.mark.asyncio
    async def test_foreign_key_constraint(self, db_session):
        """Test foreign key constraint enforces relationship integrity."""
        # Try to create related record without a main property
        non_existent_property_id = 99999999
        
        # Create related record referencing non-existent property
        invalid_misinfo = ApiPropertiesDetailsV2Misinfo(
            api_property_id=non_existent_property_id,
            branch_id=1234,
            channel="BUY"
        )
        
        db_session.add(invalid_misinfo)
        
        # Assert - Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError):
            await db_session.flush()
        
        # Roll back after the exception
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_complex_property_record(self, db_session):
        """Test creating a property with multiple complex relationships."""
        # Arrange - Create main property
        property_id = 45678901
        test_property = ApiPropertiesDetailsV2(
            id=property_id,
            transaction_type="SALE",
            bedrooms=4,
            property_type="DETACHED",
            address="Complex Property, Test City",
            summary="A complex test property",
        )
        
        # Add property and flush to generate ID
        db_session.add(test_property)
        await db_session.flush()
        
        # Create multiple related records
        misinfo = ApiPropertiesDetailsV2Misinfo(
            api_property_id=property_id,
            branch_id=7777,
            brand_plus=False,
            featured_property=True,
            channel="BUY"
        )
        
        status = ApiPropertiesDetailsV2Status(
            api_property_id=property_id,
            display_status="FOR_SALE",
            can_display_floorplans=True,
            can_display_photos=True
        )
        
        price = ApiPropertiesDetailsV2Price(
            api_property_id=property_id,
            amount=450000,
            currency_code="GBP",
            qualifier="Offers Over"
        )
        
        stamp_duty = ApiPropertiesDetailsV2StampDuty(
            api_property_id=property_id,
            effective_date="2023-01-01",
            is_second_home=False
        )
        
        features = ApiPropertiesDetailsV2Features(
            api_property_id=property_id,
            bullets=["Garden", "Garage", "Modern Kitchen", "En-suite"],
            summary="Beautiful detached house with garden and modern features"
        )
        
        branch = ApiPropertiesDetailsV2Branch(
            api_property_id=property_id,
            branch_id=7777,
            branch_name="Premium Branch",
            company_name="Luxury Properties Ltd",
            branch_postcode="TE1 1ST",
            phone_number="01234567890"
        )
        
        # Add all related records to session
        db_session.add_all([misinfo, status, price, stamp_duty, features, branch])
        await db_session.commit()
        
        # Act - Query the property with all its relationships
        result = await db_session.execute(
            select(ApiPropertiesDetailsV2).where(ApiPropertiesDetailsV2.id == property_id)
        )
        saved_property = result.scalars().first()
        
        # Assert - Check property and all relationships
        assert saved_property is not None
        assert saved_property.id == property_id
        
        # Check relationships
        assert saved_property.misinfo is not None
        assert saved_property.misinfo.branch_id == 7777
        
        assert saved_property.status is not None
        assert saved_property.status.display_status == "FOR_SALE"
        
        assert saved_property.price is not None
        assert saved_property.price.amount == 450000
        assert saved_property.price.qualifier == "Offers Over"
        
        assert saved_property.stamp_duty is not None
        assert saved_property.stamp_duty.is_second_home is False
        
        assert saved_property.features is not None
        assert len(saved_property.features.bullets) == 4
        assert "Garden" in saved_property.features.bullets
        
        assert saved_property.branch is not None
        assert saved_property.branch.branch_name == "Premium Branch"
        assert saved_property.branch.phone_number == "01234567890"
