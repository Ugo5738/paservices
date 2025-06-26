# Rightmove Data Capture Service SQL Schema

This directory contains SQL schema definitions for the Rightmove Data Capture Service database.

## Schema Overview

The `rightmove_schema.sql` file contains the full database schema definition for storing property data from the Rightmove API. It creates tables under the `rightmove` schema to keep the database organized and avoid conflicts with other services.

### Properties Detail Endpoint Tables

These tables store data from the `properties/details` API endpoint:

- `apipropertiesdetailsv2` - Main property details
- `apipropertiesdetailsagent` - Property agent information
- `apipropertiesdetailsprice` - Property price information
- `apipropertiesdetailslocation` - Property location data
- `apipropertiesdetailsimage` - Property images
- `apipropertiesdetailsfloorplan` - Property floorplans
- `apipropertiesdetailsneareststation` - Nearest stations to the property

### Property For Sale Endpoint Tables

These tables store data from the `property-for-sale/detail` API endpoint:

- `apipropertydetails` - Main property for sale details
- `apipropertydetailsprice` - Property for sale price information
- `apipropertydetailsagent` - Property for sale agent information
- `apipropertydetailsimage` - Property for sale images
- `apipropertydetailsfloorplan` - Property for sale floorplans

## Usage

### Manual Setup

To manually set up the database schema:

```bash
psql -h localhost -U postgres -d rightmove -f rightmove_schema.sql
```

### Alembic Migrations

In production environments, we recommend using Alembic migrations:

```bash
alembic upgrade head
```

This will apply all migrations, including the creation of these tables.

## Design Considerations

1. **Dedicated Schema**: All tables are in the `rightmove` schema to isolate them from other services
2. **Foreign Key Constraints**: Used to maintain referential integrity
3. **Cascade Deletion**: When a parent record is deleted, all related child records are automatically removed
4. **Automatic Timestamps**: All tables have `created_at` and `updated_at` timestamps that are automatically managed
5. **Super ID Tracking**: All tables include a `super_id` column for cross-service tracking
