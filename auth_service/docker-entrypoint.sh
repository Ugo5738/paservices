#!/bin/bash
set -e

# Set up test environment
echo "Setting up test environment..."
mkdir -p /app/test_migrations/versions

# Always copy the latest alembic configuration files
echo "Copying Alembic environment files..."
cp -f /app/alembic/env.py /app/test_migrations/env.py 
cp -f /app/alembic/script.py.mako /app/test_migrations/script.py.mako 

# Always copy all migration files from main migrations, even if destination exists
if [ -d "/app/alembic/versions" ]; then
  echo "Copying ALL migration files from alembic/versions to test_migrations/versions"
  cp -rf /app/alembic/versions/* /app/test_migrations/versions/
  
  # List the copied migration files for diagnostics
  echo "Migration files in test_migrations/versions:"
  ls -la /app/test_migrations/versions/
  echo "Total migration files copied: $(ls -1 /app/test_migrations/versions/ | wc -l)"
else
  echo "ERROR: No migration files found in /app/alembic/versions"
fi

# Set TEST_DATABASE_URL if not set
if [ -z "$TEST_DATABASE_URL" ] && [ ! -z "$DATABASE_URL" ]; then
  export TEST_DATABASE_URL="$DATABASE_URL"
  echo "Set TEST_DATABASE_URL to match DATABASE_URL: $TEST_DATABASE_URL"
fi

# Install the Python package in development mode using Poetry
echo "Installing auth_service package in development mode..."
poetry install --no-interaction

# Set PYTHONPATH to include the src directory
export PYTHONPATH=$PYTHONPATH:/app/src
echo "PYTHONPATH set to: $PYTHONPATH"

# Check if any arguments were provided
if [ $# -eq 0 ]; then
  echo "No command provided, starting default command: uvicorn"
  # Default command to keep the container running
  exec uvicorn auth_service.main:app --host 0.0.0.0 --port 8000
else
  # Execute the command provided as arguments
  echo "Running command: $@"
  exec "$@"
fi
