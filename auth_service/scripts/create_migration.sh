#!/bin/bash
set -e

echo "Creating initial migration for auth service..."

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment variables from .env.production
set -a
source "$SERVICE_DIR/.env.production"
set +a

# Set ENVIRONMENT=production for environment detection
export ENVIRONMENT=production

# First create the versions directory if it doesn't exist
mkdir -p "$SERVICE_DIR/alembic/versions"

# Clean out any existing migrations
rm -f "$SERVICE_DIR/alembic/versions"/*.py

# Install psycopg if needed (modern psycopg3 package)
echo "Installing psycopg package..."
pip install --no-cache-dir psycopg>=3.0.0

# Set PYTHONPATH to ensure module imports work correctly
export PYTHONPATH="$SERVICE_DIR/src:$PYTHONPATH"

# Create a new initial migration using the current models
cd "$SERVICE_DIR"
echo "Creating migration with database URL: $AUTH_SERVICE_DATABASE_URL"
python -m alembic revision --autogenerate -m "initial_schema"

if [ $? -eq 0 ]; then
    echo "Migration file created successfully:"
    ls -la "$SERVICE_DIR/alembic/versions"
else
    echo "Migration creation failed!"
    exit 1
fi
