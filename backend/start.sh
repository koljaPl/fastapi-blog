#!/bin/bash

# Start script for FastAPI with Uvicorn
# Usage: ./start.sh [environment]
# Example: ./start.sh production

set -e

ENVIRONMENT=${1:-development}

echo "=================================="
echo "Starting Blog Platform Backend"
echo "Environment: $ENVIRONMENT"
echo "=================================="

# Load environment variables
if [ -f .env ]; then
    echo "Loading .env file..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set environment
export ENVIRONMENT=$ENVIRONMENT

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start server based on environment
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Starting production server..."
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 4 \
        --log-level info \
        --no-access-log \
        --proxy-headers \
        --forwarded-allow-ips='*'
elif [ "$ENVIRONMENT" = "staging" ]; then
    echo "Starting staging server..."
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 2 \
        --log-level debug \
        --proxy-headers
else
    echo "Starting development server..."
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level debug
fi