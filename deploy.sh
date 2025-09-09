#!/bin/bash

# Friendly Loan Deployment Script
set -e

echo "🚀 Starting deployment of Friendly Loan..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="friendly-loan"
APP_DIR="/opt/$APP_NAME"
SERVICE_NAME="friendly-loan"
NGINX_SITE="friendly-loan"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Update system
echo -e "${YELLOW}Updating system packages...${NC}"
apt update && apt upgrade -y

# Install required packages
echo -e "${YELLOW}Installing required packages...${NC}"
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx curl

# Create application directory
echo -e "${YELLOW}Creating application directory...${NC}"
mkdir -p $APP_DIR
cd $APP_DIR

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p static/uploads
mkdir -p logs

# Set permissions
echo -e "${YELLOW}Setting permissions...${NC}"
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

# Copy systemd service
echo -e "${YELLOW}Installing systemd service...${NC}"
cp friendly-loan.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# Configure Nginx
echo -e "${YELLOW}Configuring Nginx...${NC}"
cp nginx.conf /etc/nginx/sites-available/$NGINX_SITE
ln -sf /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Start services
echo -e "${YELLOW}Starting services...${NC}"
systemctl start $SERVICE_NAME
systemctl restart nginx

# Check status
echo -e "${YELLOW}Checking service status...${NC}"
systemctl status $SERVICE_NAME --no-pager

# Setup SSL with Let's Encrypt (optional)
read -p "Do you want to setup SSL with Let's Encrypt? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter your domain name: " DOMAIN
    certbot --nginx -d $DOMAIN
fi

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo -e "${GREEN}Application is running at: http://$(hostname -I | awk '{print $1}'):80${NC}"
echo -e "${YELLOW}To check logs: journalctl -u $SERVICE_NAME -f${NC}"
echo -e "${YELLOW}To restart: systemctl restart $SERVICE_NAME${NC}"
