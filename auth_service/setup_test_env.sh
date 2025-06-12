#!/bin/bash
# This script sets up the test environment for Docker and local development

# Create test_migrations directory structure if it doesn't exist
mkdir -p test_migrations/versions

# Copy Alembic configuration files to test_migrations if they don't exist
cp -n alembic/env.py test_migrations/env.py
cp -n alembic/script.py.mako test_migrations/script.py.mako

# Only for Docker: Create a symlink to the main migration versions if the test versions are empty
if [ -z "$(ls -A test_migrations/versions)" ] && [ -d "alembic/versions" ] && [ ! -z "$(ls -A alembic/versions)" ]; then
  echo "No migration files found in test_migrations/versions, copying from main alembic/versions"
  cp -r alembic/versions/* test_migrations/versions/
fi

# Set environment variables if they don't exist
if [ -z "$TEST_DATABASE_URL" ] && [ ! -z "$DATABASE_URL" ]; then
  export TEST_DATABASE_URL="$DATABASE_URL"
  echo "Set TEST_DATABASE_URL to match DATABASE_URL"
fi

echo 'Test environment setup complete!'
