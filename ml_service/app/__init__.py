"""
Entry point for the ML service package.

This module exposes the main FastAPI application instance `ml_application`
so it can be imported and run by an ASGI server or other entry scripts.
"""
from .main import ml_application

__all__ = ["ml_application"]
