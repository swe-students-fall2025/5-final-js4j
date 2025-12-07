"""Configuration module for the API service.

This module defines application settings using Pydantic's BaseSettings.
It loads values from environment variables or defaults and exposes a
global `settings` instance used throughout the API service.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    mongo_username: str = "medqueue_user"
    mongo_password: str = "medqueue_password"
    mongo_database_name: str = "medqueue_db"
    mongo_host: str = "104.131.184.246"
    mongo_port: int = 27017

    class Config:  # pylint: disable=too-few-public-methods
        """Internal Pydantic configuration for loading environment variables."""

        env_file = ".env"


# Global settings instance used throughout the API service
settings = Settings()
