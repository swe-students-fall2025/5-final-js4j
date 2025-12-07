"""Database module providing MongoDB client and database access.

This module manages the connection to MongoDB using Motor (async client).
It maintains a module-level client cache to avoid reconnecting for each request.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

# Module-level cache for the MongoDB client instance
mongo_client_instance: AsyncIOMotorClient | None = None  # pylint: disable=invalid-name


def get_mongo_client() -> AsyncIOMotorClient:
    """
    Create or return the existing MongoDB client.

    Returns
    -------
    AsyncIOMotorClient
        A connected MongoDB client instance using configuration from
        the global `settings` object.
    """
    global mongo_client_instance  # pylint: disable=global-statement
    if mongo_client_instance is None:
        connection_string = (
            f"mongodb://{settings.mongo_username}:{settings.mongo_password}"
            f"@{settings.mongo_host}:{settings.mongo_port}/"
            f"{settings.mongo_database_name}"
            f"?authSource={settings.mongo_database_name}"
        )
        mongo_client_instance = AsyncIOMotorClient(connection_string)
    return mongo_client_instance


def close_mongo_client():
    """
    Close the MongoDB client safely. Required for testing to avoid
    'Event loop is closed' errors caused by stale async client instances.
    """
    global mongo_client_instance  # pylint: disable=global-statement
    if mongo_client_instance is not None:
        mongo_client_instance.close()
        mongo_client_instance = None


def get_database():
    """
    Return the MongoDB database object for the configured database name.

    Returns
    -------
    motor.motor_asyncio.AsyncIOMotorDatabase
        The database object corresponding to `settings.mongo_database_name`.
    """
    client_instance = get_mongo_client()
    return client_instance[settings.mongo_database_name]
