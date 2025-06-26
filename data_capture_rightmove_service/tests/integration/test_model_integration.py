"""
Integration tests for models in the data_capture_rightmove_service.
Tests the interaction between models and service layers.
"""
import uuid
import pytest
import logging
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_rightmove_service.models.properties_details_v2 import (
    ApiPropertiesDetailsV2,
    ApiPropertiesDetailsV2Misinfo,
    ApiPropertiesDetailsV2Price,
    ApiPropertiesDetailsV2Status,
    ApiPropertiesDetailsV2Features
)
from data_capture_rightmove_service.models.property_details import (
    ApiPropertyDetails,
    ApiPropertyDetailAddress,
    ApiPropertyDetailPrice
)

# Set up logger
logger = logging.getLogger(__name__)


class TestModelIntegration:
    """Test integration between models and service-level operations."""
    
    @pytest.mark.asyncio
    async def test_property_search_integration(self, db_session, seed_properties_details_v2):
        """Test searching for properties with complex criteria."""
        # Seed multiple properties with different characteristics
        await seed_properties_details_v2(
            db_session=db_session,
            property_id=1001,
            with_relations=True,
            price=250000,
            bedrooms=2,
            property_type="FLAT"
        )
        
        await seed_properties_details_v2(
            db_session=db_session,
            property_id=1002,
            with_relations=True,
            price=350000,
            bedrooms=3,
            property_type="SEMI_DETACHED"
        )
        
        await seed_properties_details_v2(
            db_session=db_session,
            property_id=1003,
            with_relations=True,
            price=450000,
            bedrooms=4,
            property_type="DETACHED"
        )
        
        await seed_properties_details_v2(
            db_session=db_session,
            property_id=1004,
            with_relations=True,
            price=300000,
            bedrooms=2,
            property_type="TERRACED"
        )
        
        # Simulate service-layer search operation
        # This mimics what a real service would do when searching for properties
        
        # Example: Find properties with 2 bedrooms under 300k
        query = (
            select(ApiPropertiesDetailsV2)
            .join(ApiPropertiesDetailsV2Price, 
                  ApiPropertiesDetailsV2.id == ApiPropertiesDetailsV2Price.api_property_id)
            .where(ApiPropertiesDetailsV2.bedrooms == 2)
            .where(ApiPropertiesDetailsV2Price.amount <= 300000)
        )
        
        result = await db_session.execute(query)
        matching_properties = result.scalars().all()
        
        # Should match properties 1001 and 1004
        assert len(matching_properties) == 2
        property_ids = [p.id for p in matching_properties]
        assert 1001 in property_ids
        assert 1004 in property_ids
        
        # Example: Find properties that are houses (not flats) over 300k
        query = (
            select(ApiPropertiesDetailsV2)
            .join(ApiPropertiesDetailsV2Price, 
                  ApiPropertiesDetailsV2.id == ApiPropertiesDetailsV2Price.api_property_id)
            .where(ApiPropertiesDetailsV2.property_type != "FLAT")
            .where(ApiPropertiesDetailsV2Price.amount > 300000)
        )
        
        result = await db_session.execute(query)
        matching_properties = result.scalars().all()
        
        # Should match properties 1002 and 1003
        assert len(matching_properties) == 2
        property_ids = [p.id for p in matching_properties]
        assert 1002 in property_ids
        assert 1003 in property_ids
    
    @pytest.mark.asyncio
    async def test_updating_property_with_relations(self, db_session, seed_properties_details_v2):
        """Test updating a property and its related records."""
        # Seed an initial property
        property_id = await seed_properties_details_v2(
            db_session=db_session,
            with_relations=True,
            price=275000,
            bedrooms=3,
            property_type="SEMI_DETACHED"
        )
        
        # Simulate service-layer update operation
        # First, retrieve the property with relations
        query = (
            select(ApiPropertiesDetailsV2)
            .where(ApiPropertiesDetailsV2.id == property_id)
        )
        result = await db_session.execute(query)
        property_to_update = result.scalars().first()
        
        # Now update various aspects of the property
        property_to_update.bedrooms = 4  # Bedroom addition
        property_to_update.summary = "Updated property summary with renovation"
        property_to_update.property_sub_type = "SEMI_DETACHED_HOUSE"
        
        # Update related price
        price_query = (
            select(ApiPropertiesDetailsV2Price)
            .where(ApiPropertiesDetailsV2Price.api_property_id == property_id)
        )
        price_result = await db_session.execute(price_query)
        price_record = price_result.scalars().first()
        
        # Increase price due to renovations
        original_price = price_record.amount
        price_record.amount = original_price + 50000
        price_record.qualifier = "Guide Price"
        
        # Add features if they don't exist
        features_query = (
            select(ApiPropertiesDetailsV2Features)
            .where(ApiPropertiesDetailsV2Features.api_property_id == property_id)
        )
        features_result = await db_session.execute(features_query)
        features = features_result.scalars().first()
        
        if features:
            # Update existing features
            features.bullets = ["Newly Renovated", "Extended Kitchen", "Garden", "Off-Street Parking"]
            features.summary = "Beautiful semi-detached house with recent renovations and extension"
        else:
            # Create new features record
            new_features = ApiPropertiesDetailsV2Features(
                api_property_id=property_id,
                bullets=["Newly Renovated", "Extended Kitchen", "Garden", "Off-Street Parking"],
                summary="Beautiful semi-detached house with recent renovations and extension"
            )
            db_session.add(new_features)
        
        # Update status to reflect changes
        status_query = (
            select(ApiPropertiesDetailsV2Status)
            .where(ApiPropertiesDetailsV2Status.api_property_id == property_id)
        )
        status_result = await db_session.execute(status_query)
        status = status_result.scalars().first()
        
        if status:
            # Ensure status is updated and published
            status.published = True
            status.display_status = "FOR_SALE"
        
        # Commit all changes
        await db_session.commit()
        
        # Verify changes persisted correctly
        # Reload property from database
        query = (
            select(ApiPropertiesDetailsV2)
            .where(ApiPropertiesDetailsV2.id == property_id)
        )
        result = await db_session.execute(query)
        updated_property = result.scalars().first()
        
        # Check base property updates
        assert updated_property.bedrooms == 4  # Was 3
        assert updated_property.summary == "Updated property summary with renovation"
        assert updated_property.property_sub_type == "SEMI_DETACHED_HOUSE"
        
        # Check price updates
        assert updated_property.price.amount == original_price + 50000
        assert updated_property.price.qualifier == "Guide Price"
        
        # Check features
        assert updated_property.features is not None
        assert len(updated_property.features.bullets) == 4
        assert "Newly Renovated" in updated_property.features.bullets
        
        # Check status
        assert updated_property.status.published is True
        assert updated_property.status.display_status == "FOR_SALE"
    
    @pytest.mark.asyncio
    async def test_aggregate_queries(self, db_session, seed_properties_details_v2):
        """Test performing aggregate queries on the property models."""
        # Seed multiple properties with different prices
        property_ids = []
        for i in range(10):
            # Create properties with varying prices based on bedrooms
            bedrooms = (i % 4) + 1
            price = 200000 + (bedrooms * 50000) + (i * 10000)
            
            # Alternate property types
            property_type = ["FLAT", "TERRACED", "SEMI_DETACHED", "DETACHED"][i % 4]
            
            property_id = await seed_properties_details_v2(
                db_session=db_session,
                with_relations=True,
                price=price,
                bedrooms=bedrooms,
                property_type=property_type
            )
            property_ids.append(property_id)
        
        # Compute average price by bedrooms - simulating an analytics query
        query = (
            select(
                ApiPropertiesDetailsV2.bedrooms,
                func.avg(ApiPropertiesDetailsV2Price.amount).label("avg_price"),
                func.count().label("count")
            )
            .join(ApiPropertiesDetailsV2Price, 
                  ApiPropertiesDetailsV2.id == ApiPropertiesDetailsV2Price.api_property_id)
            .group_by(ApiPropertiesDetailsV2.bedrooms)
            .order_by(ApiPropertiesDetailsV2.bedrooms)
        )
        
        result = await db_session.execute(query)
        stats_by_bedroom = result.all()
        
        # Assert aggregation results
        assert len(stats_by_bedroom) == 4  # Should have data for 1-4 bedrooms
        
        # Verify that bedroom counts are 1, 2, 3, 4
        bedrooms = [r[0] for r in stats_by_bedroom]
        assert sorted(bedrooms) == [1, 2, 3, 4]
        
        # Verify that average prices increase with bedroom count
        avg_prices = [r[1] for r in stats_by_bedroom]
        for i in range(1, len(avg_prices)):
            assert avg_prices[i] > avg_prices[i-1]  # Prices should increase with bedrooms
        
        # Compute distribution by property type
        type_query = (
            select(
                ApiPropertiesDetailsV2.property_type,
                func.count().label("count")
            )
            .group_by(ApiPropertiesDetailsV2.property_type)
            .order_by(func.count().desc())
        )
        
        result = await db_session.execute(type_query)
        distribution_by_type = result.all()
        
        # Should have entries for all property types
        property_types = [r[0] for r in distribution_by_type]
        assert set(property_types) == set(["FLAT", "TERRACED", "SEMI_DETACHED", "DETACHED"])
        
        # Each type should have a similar count (2-3 each)
        counts = [r[1] for r in distribution_by_type]
        assert all(count >= 2 for count in counts)
        assert sum(counts) == 10  # Total 10 properties
