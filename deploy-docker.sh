#!/bin/bash

# Docker Deployment Script for Friendly Loan
set -e

echo "🐳 Starting Docker deployment of Friendly Loan..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp env.example .env
    echo -e "${YELLOW}Please edit .env file with your configuration before continuing.${NC}"
    read -p "Press Enter to continue after editing .env file..."
fi

# Generate SSL certificates for development
echo -e "${YELLOW}Generating SSL certificates for development...${NC}"
mkdir -p ssl
if [ ! -f ssl/cert.pem ] || [ ! -f ssl/key.pem ]; then
    openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
fi

# Build and start containers
echo -e "${YELLOW}Building and starting containers...${NC}"
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
sleep 10

# Check if services are running
echo -e "${YELLOW}Checking service status...${NC}"
docker-compose ps

# Test the application
echo -e "${YELLOW}Testing application...${NC}"
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Application is running successfully!${NC}"
    echo -e "${GREEN}Application URL: https://localhost${NC}"
    echo -e "${YELLOW}Note: You may need to accept the self-signed certificate in your browser.${NC}"
else
    echo -e "${RED}❌ Application health check failed.${NC}"
    echo -e "${YELLOW}Checking logs...${NC}"
    docker-compose logs web
fi

echo -e "${GREEN}✅ Docker deployment completed!${NC}"
echo -e "${YELLOW}To view logs: docker-compose logs -f${NC}"
echo -e "${YELLOW}To stop: docker-compose down${NC}"
echo -e "${YELLOW}To restart: docker-compose restart${NC}"
