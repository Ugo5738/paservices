#!/bin/bash

# ==============================================================================
# Data Capture Rightmove Service Development Environment Setup Script
# ==============================================================================
# This script automates the entire process of setting up the local development
# environment. It ensures a clean slate by dropping and re-creating the
# databases before running migrations and starting the service.
#
# Prerequisite:
#   - Docker and Docker Compose are installed.
#   - The Supabase stack for the 'paservices' project is running.
#     (Run `supabase start` from the project's root directory).
#
# Usage:
#   ./setup_database.sh
# ==============================================================================

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
DEV_COMPOSE_FILE="docker-compose.dev.yml"
ROOT_PROJECT_DIR=".." # Assumes this script is run from inside the service directory
SUPABASE_DB_CONTAINER="supabase_db_paservices"
DEV_DB_NAME="data_capture_rightmove_dev_db"
TEST_DB_NAME="data_capture_rightmove_test_db"
SCHEMA_DUMP_FILE="sql/rightmove_schema.sql"

# --- Helper Functions ---
print_header() {
  echo ""
  echo "=============================================================================="
  echo "=> $1"
  echo "=============================================================================="
}

# --- Main Logic ---

# Step 1: Verify Supabase is running by checking for the DB container
print_header "Step 1: Verifying Supabase stack is running"
if ! docker ps --format '{{.Names}}' | grep -q "^${SUPABASE_DB_CONTAINER}$"; then
  echo "❌ ERROR: The Supabase container '${SUPABASE_DB_CONTAINER}' is not running."
  echo "Please navigate to the project root ('paservices') and run 'supabase start'."
  exit 1
fi
echo "✅ Supabase container '${SUPABASE_DB_CONTAINER}' is running."


# Step 2: Drop existing databases and create fresh ones for development and testing
# This ensures a completely clean environment for every run.
print_header "Step 2: Re-creating databases '${DEV_DB_NAME}' and '${TEST_DB_NAME}' (dropping if they exist)"

# First, clean up old databases with previous names (if they exist)
echo "Cleaning up old databases with previous names..."
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "DROP DATABASE IF EXISTS rightmove_dev_db WITH (FORCE);"
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "DROP DATABASE IF EXISTS rightmove_test_db WITH (FORCE);"
echo "✅ Old databases cleaned up."

# Using `DROP DATABASE IF EXISTS ... WITH (FORCE)` terminates any active connections
# and prevents errors if the database doesn't exist, making the script robust.
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "DROP DATABASE IF EXISTS ${DEV_DB_NAME} WITH (FORCE);"
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "CREATE DATABASE ${DEV_DB_NAME};"
echo "✅ Development database '${DEV_DB_NAME}' re-created."

docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "DROP DATABASE IF EXISTS ${TEST_DB_NAME} WITH (FORCE);"
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "CREATE DATABASE ${TEST_DB_NAME};"
echo "✅ Test database '${TEST_DB_NAME}' re-created."


# Step 3: Drop all tables in the rightmove schema if it exists
print_header "Step 3: Dropping existing tables in rightmove schema"

# Drop all tables in the rightmove schema
DROP_SCHEMA_SQL="DROP SCHEMA IF EXISTS rightmove CASCADE; CREATE SCHEMA rightmove;"
docker exec -i "${SUPABASE_DB_CONTAINER}" psql -U postgres -d "${DEV_DB_NAME}" -c "${DROP_SCHEMA_SQL}"
docker exec -i "${SUPABASE_DB_CONTAINER}" psql -U postgres -d "${TEST_DB_NAME}" -c "${DROP_SCHEMA_SQL}"
echo "✅ Schema 'rightmove' reset."

# First check if there are any existing migration files
MIGRATION_DIR="alembic/versions"
if [ -n "$(ls -A ${MIGRATION_DIR} 2>/dev/null)" ]; then
    echo "Removing existing migration files to ensure clean generation..."
    rm -f ${MIGRATION_DIR}/*.py
    echo "✅ Existing migration files removed."
fi

# We first need to build the service container to run commands in it
docker-compose -f "${DEV_COMPOSE_FILE}" build data_capture_rightmove_service_dev

# Generate a migration that will create all tables based on SQLAlchemy models
echo "Generating migration from SQLAlchemy models..."
docker-compose -f "${DEV_COMPOSE_FILE}" run --rm data_capture_rightmove_service_dev alembic revision --autogenerate -m "initial schema with all tables"
echo "✅ Migration file generated from SQLAlchemy models."

# Step 4: Apply the Alembic migration to create all tables
print_header "Step 4: Applying Alembic migration to create all tables"
docker-compose -f "${DEV_COMPOSE_FILE}" run --rm data_capture_rightmove_service_dev alembic upgrade head
echo "✅ Tables created via Alembic migration."

# Step 5: Apply custom SQL for any elements not captured in SQLAlchemy models
print_header "Step 5: Applying additional SQL customizations"
echo "Note: This step is for any SQL that can't be represented in SQLAlchemy models"
echo "      (like custom types, functions, procedures, etc.)"

# Apply any custom SQL elements that might not be captured in SQLAlchemy models
# Uncomment and modify if needed
# (cd "${ROOT_PROJECT_DIR}" && docker exec -i "${SUPABASE_DB_CONTAINER}" psql -U postgres -d "${DEV_DB_NAME}" < "data_capture_rightmove_service/sql/custom_elements.sql")
# (cd "${ROOT_PROJECT_DIR}" && docker exec -i "${SUPABASE_DB_CONTAINER}" psql -U postgres -d "${TEST_DB_NAME}" < "data_capture_rightmove_service/sql/custom_elements.sql")
echo "✅ No custom SQL elements needed at this time."

print_header "Setup Complete!"
echo "Your development environment is ready."
echo "You can now run tests with: docker-compose -f ${DEV_COMPOSE_FILE} run --rm data_capture_rightmove_service_dev pytest"