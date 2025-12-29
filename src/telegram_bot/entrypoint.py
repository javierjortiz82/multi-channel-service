"""Entrypoint module for production deployment.

This module creates the FastAPI application instance for use with uvicorn/gunicorn.
"""

from telegram_bot.app import create_app

# Create the application instance
app = create_app()
