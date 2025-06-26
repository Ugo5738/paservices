"""
Unit tests for the property_details SQLAlchemy models.
Tests database interactions and model relationships using the test database.
"""
import uuid
import pytest
import logging
from decimal import Decimal
from datetime import date
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.models.property_details import (
    ApiPropertyDetails,
    ApiPropertyDetailAddress,
    ApiPropertyDetailCustomer,
    ApiPropertyDetailDfpAdInfo,
    ApiPropertyDetailImage,
    ApiPropertyDetailFloorplan,
    ApiPropertyDetailPrice,
    ApiPropertyDetailLocation,
    ApiPropertyDetailMisInfo,
    ApiPropertyDetailStatus
)

# Set up logger
logger = logging.getLogger(__name__)


class TestPropertyDetailsModels:
    """Test suite for property_details models and their relationships."""
    
    @pytest.mark.asyncio
    async def test_create_main_property_model(self, db_session):
        """Test creating a property record with basic fields."""
        # Arrange - Create property data
        property_id = 87654321
        test_property = ApiPropertyDetails(
            id=property_id,
            transaction_type="SALE",
            bedrooms=3,
            property_type="SEMI_DETACHED",
            property_sub_type="SEMI_DETACHED_HOUSE",
            commercial=False,
            bathrooms=2,
            ai_location_info="Great location near schools and parks"
        )
        
        # Act - Save to database
        db_session.add(test_property)
        await db_session.flush()
        
        # Generate a super_id value
        test_property.super_id = uuid.uuid4()
        await db_session.commit()
        
        # Assert - Verify record was saved properly
        result = await db_session.execute(
            select(ApiPropertyDetails).where(ApiPropertyDetails.id == property_id)
        )
        saved_property = result.scalars().first()
        
        # Check field values
        assert saved_property is not None
        assert saved_property.id == property_id
        assert saved_property.transaction_type == "SALE"
        assert saved_property.bedrooms == 3
        assert saved_property.property_type == "SEMI_DETACHED"
        assert saved_property.property_sub_type == "SEMI_DETACHED_HOUSE"
        assert saved_property.commercial is False
        assert saved_property.bathrooms == 2
        assert saved_property.super_id is not None

    @pytest.mark.asyncio
    async def test_create_property_with_relationships(self, db_session):
        """Test creating a property with related records."""
        # Arrange - Create property record with ID
        property_id = 76543210
        test_property = ApiPropertyDetails(
            id=property_id,
            transaction_type="SALE",
            bedrooms=4,
            key_features=["Garden", "Garage", "Renovated Kitchen"]
        )
        
        # Add property and flush to get ID
        db_session.add(test_property)
        await db_session.flush()
        
        # Create related records
        address = ApiPropertyDetailAddress(
            api_property_detail_id=property_id,
            display_address="123 Test Lane, Testington",
            country_code="GB",
            outcode="TE1",
            incode="2AB"
        )
        
        price = ApiPropertyDetailPrice(
            api_property_detail_id=property_id,
            currency_code="GBP",
            display_price="£450,000"
        )
        
        customer = ApiPropertyDetailCustomer(
            api_property_detail_id=property_id,
            branch_id=12345,
            branch_name="Premier Properties",
            company_name="Test Real Estate Ltd",
            branch_display_name="Premier Properties - Testington",
            display_address="High Street, Testington",
            is_new_home_developer=False
        )
        
        # Add related records to session
        db_session.add_all([address, price, customer])
        await db_session.commit()
        
        # Act - Query the property with related data
        result = await db_session.execute(
            select(ApiPropertyDetails).where(ApiPropertyDetails.id == property_id)
        )
        saved_property = result.scalars().first()
        
        # Assert - Check relationships loaded correctly
        assert saved_property is not None
        
        # Check each relationship
        assert saved_property.address is not None
        assert saved_property.address.display_address == "123 Test Lane, Testington"
        assert saved_property.address.country_code == "GB"
        
        assert saved_property.price is not None
        assert saved_property.price.currency_code == "GBP"
        assert saved_property.price.display_price == "£450,000"
        
        assert saved_property.customer is not None
        assert saved_property.customer.branch_id == 12345
        assert saved_property.customer.company_name == "Test Real Estate Ltd"

    @pytest.mark.asyncio
    async def test_cascade_delete(self, db_session):
        """Test cascade delete behavior between property and related tables."""
        # Arrange - Create property with related records
        property_id = 65432109
        
        # Create main property
        test_property = ApiPropertyDetails(
            id=property_id,
            transaction_type="SALE",
            bedrooms=3,
        )
        
        # Add property and flush to generate ID
        db_session.add(test_property)
        await db_session.flush()
        
        # Create related records
        mis_info = ApiPropertyDetailMisInfo(
            api_property_detail_id=property_id,
            branch_id=54321,
            brand_plus=True,
            featured_property=True
        )
        
        location = ApiPropertyDetailLocation(
            api_property_detail_id=property_id,
            latitude=Decimal("51.5074"),
            longitude=Decimal("-0.1278"),
            circle_radius_on_map=1000,
            show_map=True
        )
        
        # Add images
        image1 = ApiPropertyDetailImage(
            api_property_detail_id=property_id,
            url="https://example.com/image1.jpg",
            caption="Front of property"
        )
        
        image2 = ApiPropertyDetailImage(
            api_property_detail_id=property_id,
            url="https://example.com/image2.jpg",
            caption="Kitchen" 
        )
        
        # Add related records to session
        db_session.add_all([mis_info, location, image1, image2])
        await db_session.commit()
        
        # Act - Delete the main property record
        property_to_delete = (await db_session.execute(
            select(ApiPropertyDetails).where(ApiPropertyDetails.id == property_id)
        )).scalars().first()
        
        # Verify images were created correctly first
        image_count = await db_session.execute(
            select(ApiPropertyDetailImage).where(ApiPropertyDetailImage.api_property_detail_id == property_id)
        )
        assert len(image_count.scalars().all()) == 2
        
        # Now delete the property
        await db_session.delete(property_to_delete)
        await db_session.commit()
        
        # Assert - Verify cascade delete worked
        # Check main property is gone
        property_check = (await db_session.execute(
            select(ApiPropertyDetails).where(ApiPropertyDetails.id == property_id)
        )).scalars().first()
        assert property_check is None
        
        # Check related records are gone
        misinfo_check = (await db_session.execute(
            select(ApiPropertyDetailMisInfo).where(ApiPropertyDetailMisInfo.api_property_detail_id == property_id)
        )).scalars().first()
        assert misinfo_check is None
        
        location_check = (await db_session.execute(
            select(ApiPropertyDetailLocation).where(ApiPropertyDetailLocation.api_property_detail_id == property_id)
        )).scalars().first()
        assert location_check is None
        
        # Check that one-to-many relationships are also deleted
        images_check = (await db_session.execute(
            select(ApiPropertyDetailImage).where(ApiPropertyDetailImage.api_property_detail_id == property_id)
        )).scalars().all()
        assert len(images_check) == 0

    @pytest.mark.asyncio
    async def test_foreign_key_constraint(self, db_session):
        """Test foreign key constraint enforces relationship integrity."""
        # Try to create related record without a main property
        non_existent_property_id = 11111111
        
        # Create related record referencing non-existent property
        invalid_address = ApiPropertyDetailAddress(
            api_property_detail_id=non_existent_property_id,
            display_address="Invalid Address",
            country_code="GB"
        )
        
        db_session.add(invalid_address)
        
        # Assert - Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError):
            await db_session.flush()
        
        # Roll back after the exception
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_one_to_many_relationships(self, db_session):
        """Test one-to-many relationships like images and floorplans."""
        # Arrange - Create property
        property_id = 54321098
        test_property = ApiPropertyDetails(
            id=property_id,
            transaction_type="SALE",
            bedrooms=5,
            property_type="DETACHED"
        )
        
        # Add property and flush to get ID
        db_session.add(test_property)
        await db_session.flush()
        
        # Add multiple images
        images = [
            ApiPropertyDetailImage(
                api_property_detail_id=property_id,
                url=f"https://example.com/image{i}.jpg",
                caption=f"Image {i}",
                order_index=i
            )
            for i in range(1, 6)  # Create 5 images
        ]
        
        # Add multiple floorplans
        floorplans = [
            ApiPropertyDetailFloorplan(
                api_property_detail_id=property_id,
                url=f"https://example.com/floorplan{i}.jpg",
                caption=f"Floorplan {i}",
                order_index=i
            )
            for i in range(1, 3)  # Create 2 floorplans
        ]
        
        # Add all records
        db_session.add_all(images + floorplans)
        await db_session.commit()
        
        # Act - Query the property with its collections
        result = await db_session.execute(
            select(ApiPropertyDetails).where(ApiPropertyDetails.id == property_id)
        )
        saved_property = result.scalars().first()
        
        # Assert - Check collections are loaded correctly
        assert saved_property is not None
        
        # Check images collection
        assert len(saved_property.images) == 5
        # Verify images are ordered by order_index
        image_order = [img.order_index for img in saved_property.images]
        assert image_order == sorted(image_order)  # Should be in ascending order
        
        # Check floorplans collection
        assert len(saved_property.floorplans) == 2
        
        # Check specific image properties
        test_image = saved_property.images[0]  # Get first image
        assert test_image.url.startswith("https://example.com/image")
        assert test_image.caption.startswith("Image")

    @pytest.mark.asyncio
    async def test_complex_property_record(self, db_session):
        """Test creating a property with multiple complex relationships."""
        # Arrange - Create main property
        property_id = 43210987
        test_property = ApiPropertyDetails(
            id=property_id,
            transaction_type="SALE",
            bedrooms=6,
            bathrooms=4,
            property_type="DETACHED",
            property_sub_type="DETACHED_HOUSE",
            commercial=False,
            business_for_sale=False,
            key_features=["Swimming Pool", "Cinema Room", "Private Garden", 
                          "Double Garage", "Underfloor Heating"],
            brochures={"url": "https://example.com/brochure.pdf"},
            commercial_use_classes=None
        )
        
        # Add property and flush to generate ID
        db_session.add(test_property)
        await db_session.flush()
        
        # Create multiple related records
        address = ApiPropertyDetailAddress(
            api_property_detail_id=property_id,
            display_address="Luxury Villa, Test Boulevard",
            country_code="GB",
            outcode="TE1",
            incode="3ST",
            uk_country="England"
        )
        
        price = ApiPropertyDetailPrice(
            api_property_detail_id=property_id,
            currency_code="GBP",
            display_price="£1,250,000"
        )
        
        customer = ApiPropertyDetailCustomer(
            api_property_detail_id=property_id,
            branch_id=99999,
            branch_name="Luxury Real Estate",
            company_name="Premium Properties International",
            display_address="Victory House, Central Plaza, London",
            logo_path="https://example.com/logo.png"
        )
        
        location = ApiPropertyDetailLocation(
            api_property_detail_id=property_id,
            latitude=Decimal("52.4068"),
            longitude=Decimal("-1.5197"),
            circle_radius_on_map=1500,
            show_map=True,
            zoom_level=14
        )
        
        mis_info = ApiPropertyDetailMisInfo(
            api_property_detail_id=property_id,
            branch_id=99999,
            brand_plus=True,
            featured_property=True,
            premium_display=True
        )
        
        status = ApiPropertyDetailStatus(
            api_property_detail_id=property_id,
            published=True,
            saved=False
        )
        
        # Add all related records to session
        db_session.add_all([
            address, price, customer, location, 
            mis_info, status
        ])
        
        # Add images
        for i in range(1, 8):  # Add 7 images
            image = ApiPropertyDetailImage(
                api_property_detail_id=property_id,
                url=f"https://example.com/luxury_image{i}.jpg",
                caption=f"Luxury Property Image {i}",
                order_index=i
            )
            db_session.add(image)
            
        # Add floorplans
        for i in range(1, 4):  # Add 3 floorplans
            floorplan = ApiPropertyDetailFloorplan(
                api_property_detail_id=property_id,
                url=f"https://example.com/luxury_floorplan{i}.jpg",
                caption=f"Floor {i}",
                type="FLOORPLAN",
                order_index=i
            )
            db_session.add(floorplan)
            
        # Add mapping info
        dfp_ad_info = ApiPropertyDetailDfpAdInfo(
            api_property_detail_id=property_id,
            channel="SALE",
            targeting={"premium": True, "featured": True}
        )
        db_session.add(dfp_ad_info)
        
        await db_session.commit()
        
        # Act - Query the property with all its relationships
        result = await db_session.execute(
            select(ApiPropertyDetails).where(ApiPropertyDetails.id == property_id)
        )
        saved_property = result.scalars().first()
        
        # Assert - Check property and all relationships
        assert saved_property is not None
        assert saved_property.id == property_id
        
        # Check base properties
        assert saved_property.bedrooms == 6
        assert len(saved_property.key_features) == 5
        assert "Swimming Pool" in saved_property.key_features
        
        # Check relationships
        assert saved_property.address is not None
        assert saved_property.address.display_address == "Luxury Villa, Test Boulevard"
        
        assert saved_property.price is not None
        assert saved_property.price.display_price == "£1,250,000"
        
        assert saved_property.customer is not None
        assert saved_property.customer.branch_name == "Luxury Real Estate"
        
        assert saved_property.location is not None
        assert float(saved_property.location.latitude) == pytest.approx(52.4068)
        
        assert saved_property.dfp_ad_info is not None
        assert saved_property.dfp_ad_info.targeting["premium"] is True
        
        # Check collections
        assert len(saved_property.images) == 7
        assert len(saved_property.floorplans) == 3
