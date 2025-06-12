#!/bin/bash
set -e

echo "Starting Super ID Service entrypoint script..."

# If we're running tests, initialize the test database
if [ "$1" = "pytest" ] || [ "$1" = "test" ]; then
    echo "Setting up test environment..."
    
    # Ensure we have a proper test database
    python /app/scripts/super_id_test_migrations.py
    
    # Run the tests with any additional arguments
    shift
    exec pytest "$@"
else
    # For normal API server operation
    echo "Starting Super ID Service API..."
    exec uvicorn super_id_service.main:app --host 0.0.0.0 --port 8000 --reload
fi
