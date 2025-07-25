#!/bin/bash

# Deployment validation script for the auth service
set -e

echo "==== Auth Service Deployment Test ===="
echo "Testing production configuration..."

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    echo "❌ ERROR: .env.prod file not found. Please create it from .env.prod.example"
    exit 1
fi

# Verify Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ ERROR: Docker is not installed or not in PATH"
    exit 1
fi

# Verify docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ ERROR: docker-compose is not installed or not in PATH"
    exit 1
fi

# Validate docker-compose file syntax
echo "Validating docker-compose.prod.yml syntax..."
docker-compose -f docker-compose.prod.yml config > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ ERROR: docker-compose.prod.yml has syntax errors"
    exit 1
fi
echo "✅ docker-compose.prod.yml syntax is valid"

# Check if we're using self-hosted Supabase
SELF_HOSTED=$(grep "AUTH_SERVICE_SUPABASE_SELF_HOSTED=true" .env.prod || echo "")
if [ -n "$SELF_HOSTED" ]; then
    echo "Self-hosted Supabase configuration detected"
    
    # Check for required self-hosted variables
    MISSING_VARS=false
    
    if ! grep -q "AUTH_SERVICE_SUPABASE_DB_HOST" .env.prod; then
        echo "❌ ERROR: AUTH_SERVICE_SUPABASE_DB_HOST not found in .env.prod"
        MISSING_VARS=true
    fi
    
    if ! grep -q "AUTH_SERVICE_SUPABASE_DB_PASSWORD" .env.prod; then
        echo "❌ ERROR: AUTH_SERVICE_SUPABASE_DB_PASSWORD not found in .env.prod"
        MISSING_VARS=true
    fi
    
    if [ "$MISSING_VARS" = true ]; then
        echo "Please set all required self-hosted Supabase variables in .env.prod"
        exit 1
    fi
    
    echo "✅ Self-hosted Supabase configuration appears valid"
    
    # Check if the Supabase network exists
    NETWORK_EXISTS=$(docker network ls | grep supabase_network || echo "")
    if [ -z "$NETWORK_EXISTS" ]; then
        echo "⚠️ WARNING: supabase_network Docker network not found"
        echo "   You will need to ensure this network exists or modify docker-compose.prod.yml"
        echo "   to match your self-hosted Supabase network name"
    else
        echo "✅ supabase_network exists"
    fi
fi

# Build the Docker image to verify it builds correctly
echo "Building Docker image to test build process..."
docker-compose -f docker-compose.prod.yml build auth_service
if [ $? -ne 0 ]; then
    echo "❌ ERROR: Failed to build Docker image"
    exit 1
fi
echo "✅ Docker image builds successfully"

# All tests passed
echo "✅ Deployment configuration tests passed!"
echo "The service appears ready for deployment."
echo "Run 'docker-compose -f docker-compose.prod.yml up -d' to deploy"
