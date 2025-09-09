#!/usr/bin/env python3
"""
WSGI entry point for production deployment
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set environment
os.environ.setdefault('FLASK_ENV', 'production')

from app import app

if __name__ == "__main__":
    app.run()
