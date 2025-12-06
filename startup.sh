#!/bin/bash
# Azure App Service startup script

echo "Starting Gunicorn..."

# Increase worker timeout for ML model loading
gunicorn --bind=0.0.0.0:8000 \
  --workers=1 \
  --threads=2 \
  --timeout=600 \
  --preload \
  --access-logfile '-' \
  --error-logfile '-' \
  wsgi:app
