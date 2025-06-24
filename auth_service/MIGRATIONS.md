# Auth Service Migration Workflow

This document outlines the database migration workflow for the `auth_service` component of the Paservices platform. The auth_service has a key dependency on Supabase's auth schema and requires a specific setup process to manage migrations correctly.

## Architecture Overview

The auth_service database schema consists of two parts:

1. **External Auth Schema**: Managed by Supabase, containing tables like `auth.users`
2. **Auth Service Tables**: Managed by our application through Alembic, containing our custom tables

## Migration Setup Process

### Step 1: Set Up External Auth Schema

The auth schema must be set up before running Alembic migrations. This schema is managed by Supabase and contains critical tables like `auth.users`.

```bash
# Copy the auth schema from the source database to your target database
python scripts/copy_auth_schema.py --source-db postgres --target-db auth_dev_db --host 127.0.0.1 --port 54322
```

This script:

- Creates the `auth` schema in the target database
- Copies table definitions from a source database with Supabase auth
- Creates a test user if needed
- Ensures required columns exist in `auth.users`

### Step 2: Configure Alembic

Ensure `alembic.ini` points to the correct database:

```ini
# in alembic.ini
sqlalchemy.url = postgresql+psycopg://postgres:postgres@127.0.0.1:54322/auth_dev_db
```

Ensure `env.py` is configured to:

1. Import all models
2. Set `target_metadata = Base.metadata`
3. Handle async database connections correctly

### Step 3: Generate and Apply Migrations

```bash
# Generate new migration
alembic revision --autogenerate -m "describe_your_changes"

# Apply migrations
alembic upgrade head
```

**Important Note**: Alembic-generated migrations may attempt to create `auth.users` table that already exists. You may need to modify the migration file to skip this table creation, as done in our setup.

### Step 4: Verify Migrations

After applying migrations, verify that the database schema matches your SQLAlchemy models:

```bash
python scripts/verify_migrations.py
```

This script:

- Extracts expected schema from SQLAlchemy models
- Compares with the actual database schema
- Reports any discrepancies (missing tables or columns)

## Handling Model Changes

When changing models:

1. Update SQLAlchemy models in `src/auth_service/models/`
2. Generate a new migration: `alembic revision --autogenerate -m "describe_changes"`
3. Review the generated migration file for accuracy
   - Watch for external schema references (`auth` schema)
   - Ensure proper relationship handling
4. Apply the migration: `alembic upgrade head`
5. Verify using the verification script

## Common Issues and Solutions

### Circular Import Issues

- Use string-based relationship references (`"src.auth_service.models.SomeModel"`)
- Import models through `src.auth_service.models` module (preferred), not directly
- Ensure models are correctly registered with `Base.metadata`

### Auth Schema Issues

- The `auth` schema is managed by Supabase, not Alembic
- Always run the `copy_auth_schema.py` script before migrations on a fresh database
- If migrations try to create `auth` tables, modify the migration to skip them

### Database URL Configuration

- Ensure the database URL in `alembic.ini` points to the correct database
- For local development, use: `postgresql+psycopg://postgres:postgres@127.0.0.1:54322/auth_dev_db`
- For production, use environment variables to configure the URL

## Complete Workflow Example

For a new developer setting up migrations from scratch:

```bash
# 1. Create a fresh development database
createdb -h 127.0.0.1 -p 54322 -U postgres auth_dev_db

# 2. Set up the auth schema (Supabase tables)
python scripts/copy_auth_schema.py --source-db postgres --target-db auth_dev_db --host 127.0.0.1 --port 54322

# 3. Apply all migrations
alembic upgrade head

# 4. Verify migrations applied correctly
python scripts/verify_migrations.py
```

## Adding New Migrations

When making schema changes:

```bash
# 1. Update your SQLAlchemy models

# 2. Generate new migration
alembic revision --autogenerate -m "describe_your_changes"

# 3. Review the generated migration file
# Modify if needed (especially if it tries to change auth schema tables)

# 4. Apply the migration
alembic upgrade head

# 5. Verify changes
python scripts/verify_migrations.py
```

## Script Reference

- **copy_auth_schema.py**: Sets up the external `auth` schema from Supabase
- **verify_migrations.py**: Verifies that the database schema matches SQLAlchemy models
- **create_migration.sh**: Helper script to create initial migrations
- **auth_test_migrations.py**: Script for setting up test database migrations
