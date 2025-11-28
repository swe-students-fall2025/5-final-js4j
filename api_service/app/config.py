from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    mongo_username: str = "medqueue_user"
    mongo_password: str = "medqueue_password"
    mongo_database_name: str = "medqueue_db"
    mongo_host: str = "mongo_database"
    mongo_port: int = 27017

    class Config:
        """Internal Pydantic configuration for loading environment variables."""

        env_file = ".env"


settings = Settings()
"""
Global settings instance used by the API service to access configuration
values such as MongoDB credentials and host information.
"""
