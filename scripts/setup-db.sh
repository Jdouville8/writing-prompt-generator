#!/bin/bash

# Database Setup Script for Writing Prompt Generator
# This script initializes the PostgreSQL database with required tables

echo "🚀 Starting Database Setup..."

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
until docker exec writing-prompt-generator-postgres-1 pg_isready -U promptuser > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo ""
echo -e "${GREEN}✓ PostgreSQL is ready!${NC}"

# Run the SQL script
echo "🔨 Creating database tables..."
docker exec -i writing-prompt-generator-postgres-1 psql -U promptuser -d writingprompts < scripts/init-db.sql

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database tables created successfully!${NC}"
else
    echo -e "${RED}✗ Failed to create database tables${NC}"
    exit 1
fi

# Verify tables were created
echo "🔍 Verifying database setup..."
docker exec writing-prompt-generator-postgres-1 psql -U promptuser -d writingprompts -c "\dt"

echo -e "${GREEN}✅ Database setup complete!${NC}"