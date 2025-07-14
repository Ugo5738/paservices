--
-- DATABASE SCHEMA FOR PROPERTY-FOR-SALE API
--
-- This schema uses a hybrid approach:
-- 1. Main Table (`property_listings`): Flattens nested objects with a one-to-one relationship.
-- 2. Child Tables: Creates separate tables for arrays of objects (one-to-many relationships)
--    to maintain normalization and avoid data duplication.
--
-- This design is optimized for both data integrity and query performance.
--

-- Create the schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS rightmove;

-- =================================================================================
-- Table 1: property_listings
-- The central table for all property listings.
-- =================================================================================
CREATE TABLE rightmove.property_listings (
    snapshot_id BIGSERIAL PRIMARY KEY,
    id BIGINT NOT NULL,
    super_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    api_source_endpoint VARCHAR(100) NOT NULL, -- e.g., 'property-for-sale'

    -- Top-Level Property Attributes
    added_or_reduced VARCHAR(255),
    auction BOOLEAN,
    bathrooms INT,
    bedrooms INT,
    channel VARCHAR(50),
    commercial BOOLEAN,
    contact_url TEXT,
    country_code VARCHAR(10),
    development BOOLEAN,
    display_address VARCHAR(512),
    display_size VARCHAR(100),
    display_status VARCHAR(255),
    distance DECIMAL(10, 4),
    enhanced_listing BOOLEAN,
    enquired_timestamp TIMESTAMP,
    featured_property BOOLEAN,
    fees_apply BOOLEAN,
    fees_apply_text TEXT,
    first_visible_date TIMESTAMP,
    formatted_branch_name VARCHAR(255),
    formatted_distance VARCHAR(100),
    has_brand_plus BOOLEAN,
    heading TEXT,
    hidden BOOLEAN,
    is_recent BOOLEAN,
    keyword_match_type VARCHAR(100),
    keywords_json JSONB, -- Stores the 'keywords' array as JSON
    number_of_floorplans INT,
    number_of_images INT,
    number_of_virtual_tours INT,
    online_viewings_available BOOLEAN,
    premium_listing BOOLEAN,
    property_sub_type VARCHAR(100),
    property_type_full_description VARCHAR(255),
    property_url TEXT,
    residential BOOLEAN,
    saved BOOLEAN,
    show_on_map BOOLEAN,
    static_map_url TEXT,
    students BOOLEAN,
    summary TEXT,
    transaction_type VARCHAR(50),

    -- Flattened 'customer' object fields
    customer_branch_display_name VARCHAR(255),
    customer_branch_id INT,
    customer_branch_landing_page_url TEXT,
    customer_branch_name VARCHAR(255),
    customer_brand_plus_logo_uri TEXT,
    customer_brand_plus_logo_url TEXT,
    customer_brand_trading_name VARCHAR(255),
    customer_build_to_rent BOOLEAN,
    customer_build_to_rent_benefits_json JSONB, -- Stores the 'buildToRentBenefits' array
    customer_commercial BOOLEAN,
    customer_contact_telephone VARCHAR(50),
    customer_development BOOLEAN,
    customer_development_content TEXT,
    customer_enhanced_listing BOOLEAN,
    customer_show_on_map BOOLEAN,
    customer_show_reduced_properties BOOLEAN,

    -- Flattened 'listingUpdate' object fields
    listing_update_date TIMESTAMP,
    listing_update_reason VARCHAR(100),

    -- Flattened 'location' object fields
    location_latitude DECIMAL(10, 8),
    location_longitude DECIMAL(11, 8),

    -- Flattened 'lozengeModel' object fields
    lozenge_model_matching_lozenges_json JSONB, -- Stores the 'matchingLozenges' array

    -- Flattened 'price' object fields (1-to-1 data)
    price_amount DECIMAL(14, 2),
    price_currency_code VARCHAR(10),
    price_frequency VARCHAR(50),

    -- Flattened 'productLabel' object fields
    product_label_text VARCHAR(255),
    product_label_spotlight_label BOOLEAN,
    
    -- Flattened 'propertyImages' object fields (1-to-1 data)
    property_images_main_image_src TEXT,
    property_images_main_map_image_src TEXT
);


-- =================================================================================
-- Table 2: property_display_prices
-- Stores the 'displayPrices' array from the 'price' object.
-- Each property can have multiple display price entries.
-- =================================================================================
CREATE TABLE rightmove.property_display_prices (
    id SERIAL PRIMARY KEY,
    property_listing_snapshot_id BIGINT NOT NULL,
    super_id UUID NOT NULL,
    display_price VARCHAR(100),
    display_price_qualifier VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (property_listing_snapshot_id) REFERENCES rightmove.property_listings(snapshot_id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX idx_property_display_prices_snapshot_id ON rightmove.property_display_prices(property_listing_snapshot_id);
CREATE INDEX idx_property_display_prices_super_id ON rightmove.property_display_prices(super_id);


-- =================================================================================
-- Table 3: property_images
-- Stores the list of images from the 'propertyImages.images' array.
-- Each property can have multiple images.
-- =================================================================================
CREATE TABLE rightmove.property_images (
    id SERIAL PRIMARY KEY,
    property_listing_snapshot_id BIGINT NOT NULL,
    super_id UUID NOT NULL,
    caption VARCHAR(255),
    src_url TEXT,
    url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (property_listing_snapshot_id) REFERENCES rightmove.property_listings(snapshot_id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX idx_property_images_snapshot_id ON rightmove.property_images(property_listing_snapshot_id);
CREATE INDEX idx_property_images_super_id ON rightmove.property_images(super_id);

-- Create indexes for the main table
CREATE INDEX idx_property_listings_id ON rightmove.property_listings(id);
CREATE INDEX idx_property_listings_super_id ON rightmove.property_listings(super_id);