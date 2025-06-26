#!/bin/bash

# ==============================================================================
# Data Capture Rightmove Service Test Environment Setup Script
# ==============================================================================
# This script automates the entire process of setting up the test environment,
# from creating databases to running migrations and preparing for tests.
#
# Prerequisite:
#   - Docker and Docker Compose are installed.
#
# Usage:
#   ./setup_test_env.sh
# ==============================================================================

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
TEST_COMPOSE_FILE="docker-compose.test.yml"

# --- Helper Functions ---
print_header() {
  echo ""
  echo "=============================================================================="
  echo "=> $1"
  echo "=============================================================================="
}

print_header "Rightmove Data Capture Service Test Environment Setup"
echo -e "Setting up test environment in ${YELLOW}$SERVICE_ROOT${NC}\n"

# --- Main Logic ---

# Step 1: Check for env.test file
print_header "Step 1: Checking for env.test file"
if [ ! -f "env.test" ]; then
  echo "❌ ERROR: env.test file not found."
  echo "Please create an env.test file with the necessary environment variables."
  exit 1
fi
echo "✅ env.test file found."

# Step 2: Start Postgres and Redis containers for testing
print_header "Step 2: Starting PostgreSQL and Redis containers for testing"
echo "Starting test infrastructure containers..."
docker-compose -f "${TEST_COMPOSE_FILE}" up -d postgres_test redis_test
echo "✅ Test infrastructure containers started."

# Step 3: Wait for PostgreSQL to be ready
print_header "Step 3: Waiting for PostgreSQL to be ready"
MAX_RETRIES=30
RETRY_COUNT=0
echo "Checking PostgreSQL readiness..."

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if docker-compose -f "${TEST_COMPOSE_FILE}" exec postgres_test pg_isready -U postgres &>/dev/null; then
    echo "✅ PostgreSQL is ready!"
    break
  fi
  echo "Waiting for PostgreSQL to start... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
  RETRY_COUNT=$((RETRY_COUNT + 1))
  sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "❌ ERROR: PostgreSQL failed to start within the allocated time."
  exit 1
fi

# Step 4: Create the schema for the database
print_header "Step 4: Creating 'rightmove' schema in the test database"
docker-compose -f "${TEST_COMPOSE_FILE}" exec postgres_test psql -U postgres -d rightmove_test -c "CREATE SCHEMA IF NOT EXISTS rightmove;"
echo "✅ Schema created or already exists."

# Step 5: Run Alembic migrations to create test tables
print_header "Step 5: Running Alembic migrations for test database"
# We need to build the test container first
docker-compose -f "${TEST_COMPOSE_FILE}" build data_capture_rightmove_test
# Now run the migrations
docker-compose -f "${TEST_COMPOSE_FILE}" run --rm data_capture_rightmove_test alembic upgrade head
echo "✅ Alembic migrations applied to test database."

print_header "Test Setup Complete!"
echo "Your test environment is ready."
echo "To run tests, use: docker-compose -f ${TEST_COMPOSE_FILE} run --rm data_capture_rightmove_test pytest"
