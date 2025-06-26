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
#   ./setup_dev_env.sh
# ==============================================================================

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
DEV_COMPOSE_FILE="docker-compose.dev.yml"
ROOT_PROJECT_DIR=".." # Assumes this script is run from inside the auth_service directory
SUPABASE_DB_CONTAINER="supabase_db_paservices"
DEV_DB_NAME="rightmove_dev_db"
TEST_DB_NAME="rightmove_test_db"
SCHEMA_DUMP_FILE="data_capture_rightmove_service/sql/rightmove_schema.sql"

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

# Using `DROP DATABASE IF EXISTS ... WITH (FORCE)` terminates any active connections
# and prevents errors if the database doesn't exist, making the script robust.
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "DROP DATABASE IF EXISTS ${DEV_DB_NAME} WITH (FORCE);"
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "CREATE DATABASE ${DEV_DB_NAME};"
echo "✅ Development database '${DEV_DB_NAME}' re-created."

docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "DROP DATABASE IF EXISTS ${TEST_DB_NAME} WITH (FORCE);"
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "CREATE DATABASE ${TEST_DB_NAME};"
echo "✅ Test database '${TEST_DB_NAME}' re-created."


# Step 3: Apply the 'rightmove' schema to our new databases
print_header "Step 3: Applying 'rightmove' schema to dev and test databases"
# We run this from the parent directory context to ensure the paths are correct
(cd "${ROOT_PROJECT_DIR}" && docker exec -i "${SUPABASE_DB_CONTAINER}" psql -U postgres -d "${DEV_DB_NAME}" < "data_capture_rightmove_service/${SCHEMA_DUMP_FILE}")
(cd "${ROOT_PROJECT_DIR}" && docker exec -i "${SUPABASE_DB_CONTAINER}" psql -U postgres -d "${TEST_DB_NAME}" < "data_capture_rightmove_service/${SCHEMA_DUMP_FILE}")
echo "✅ 'rightmove' schema applied."


# Step 4: Run Alembic migrations to create our application's tables
print_header "Step 4: Running Alembic migrations for application tables"
# We first need to build the service container to run commands in it
docker-compose -f "${DEV_COMPOSE_FILE}" build data_capture_rightmove_service_dev
# Now execute the alembic command
docker-compose -f "${DEV_COMPOSE_FILE}" run --rm data_capture_rightmove_service_dev alembic upgrade head
echo "✅ Alembic migrations applied."

print_header "Setup Complete!"
echo "Your development environment is ready."
echo "You can now run tests with: docker-compose -f ${DEV_COMPOSE_FILE} run --rm data_capture_rightmove_service_dev pytest"