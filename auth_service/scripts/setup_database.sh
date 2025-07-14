#!/bin/bash

# ==============================================================================
# Auth Service Development Environment Setup Script
# ==============================================================================
# This script automates the entire process of setting up the local development
# environment, from creating databases to running migrations and starting the
# service.
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
DEV_DB_NAME="auth_dev_db"
TEST_DB_NAME="auth_test_db"
SCHEMA_DUMP_FILE="scripts/auth_schema.sql"

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


# Step 2: Create the dedicated databases for development and testing
print_header "Step 2: Creating databases '${DEV_DB_NAME}' and '${TEST_DB_NAME}'"
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "CREATE DATABASE ${DEV_DB_NAME};" || echo "Database '${DEV_DB_NAME}' already exists or failed to create."
docker exec "${SUPABASE_DB_CONTAINER}" psql -U postgres -c "CREATE DATABASE ${TEST_DB_NAME};" || echo "Database '${TEST_DB_NAME}' already exists or failed to create."
echo "✅ Databases are present."


# Step 3: Dump the 'auth' schema from the main 'postgres' database
print_header "Step 3: Creating a blueprint of the Supabase 'auth' schema"
# We run this from the parent directory context to ensure the paths are correct
(cd "${ROOT_PROJECT_DIR}" && docker exec "${SUPABASE_DB_CONTAINER}" pg_dump -U postgres -d postgres --schema=auth --no-owner --no-privileges --schema-only > "auth_service/${SCHEMA_DUMP_FILE}")
if [ -s "${SCHEMA_DUMP_FILE}" ]; then
  echo "✅ Successfully dumped 'auth' schema to '${SCHEMA_DUMP_FILE}'."
else
  echo "❌ ERROR: Failed to dump 'auth' schema. The dump file is empty."
  exit 1
fi


# Step 4: Apply the 'auth' schema to our new databases
print_header "Step 4: Applying 'auth' schema to dev and test databases"
# We run this from the parent directory context to ensure the paths are correct
(cd "${ROOT_PROJECT_DIR}" && docker exec -i "${SUPABASE_DB_CONTAINER}" psql -U postgres -d "${DEV_DB_NAME}" < "auth_service/${SCHEMA_DUMP_FILE}")
(cd "${ROOT_PROJECT_DIR}" && docker exec -i "${SUPABASE_DB_CONTAINER}" psql -U postgres -d "${TEST_DB_NAME}" < "auth_service/${SCHEMA_DUMP_FILE}")
echo "✅ 'auth' schema applied."


# Step 5: Run Alembic migrations to create our application's tables
print_header "Step 5: Running Alembic migrations for application tables"
# We first need to build the service container to run commands in it
docker-compose -f "${DEV_COMPOSE_FILE}" build auth_service_dev
# Now execute the alembic command
docker-compose -f "${DEV_COMPOSE_FILE}" exec auth_service_dev alembic upgrade head
echo "✅ Alembic migrations applied."


# Step 6: Start the service and run bootstrap
print_header "Step 6: Starting the auth_service container"
# The `--remove-orphans` flag cleans up any old containers.
docker-compose -f "${DEV_COMPOSE_FILE}" up --build -d --remove-orphans
echo "✅ Service is starting. Checking logs for confirmation..."
# Give it a few seconds to initialize
sleep 5
docker-compose -f "${DEV_COMPOSE_FILE}" logs --tail="50" auth_service_dev
echo "✅ Service started. Review logs above for any startup errors."

print_header "Setup Complete!"
echo "Your development environment is ready."
echo "You can now run tests with: docker-compose -f ${DEV_COMPOSE_FILE} exec auth_service_dev pytest"