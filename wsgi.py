"""
WSGI entry point for production deployment.
Use with gunicorn: gunicorn wsgi:app
"""
import os
from app import create_app

# Set default environment to production
os.environ.setdefault('FLASK_ENV', 'production')

app = create_app()

if __name__ == '__main__':
    app.run()
