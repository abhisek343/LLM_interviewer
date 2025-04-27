# LLM_interviewer/server/app/db/mongodb.py

import logging
from typing import Optional # Import Optional for type hinting

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# Import settings for configuration
from app.core.config import settings

logger = logging.getLogger(__name__)

class MongoDB:
    """
    Singleton class to manage the MongoDB connection lifecycle.
    """
    # Add type hints for client and db attributes
    client: Optional[AsyncIOMotorClient]
    db: Optional[AsyncIOMotorDatabase]

    def __init__(self):
        """Initializes the MongoDB manager with None client/db."""
        self.client = None
        self.db = None
        # Use settings directly for configuration
        self.mongodb_url = settings.MONGODB_URL
        self.mongodb_db_name = settings.MONGODB_DB
        logger.info("MongoDB manager initialized.")

    async def connect(self):
        """
        Establishes connection to MongoDB using settings.
        Initializes the client and db attributes upon successful connection.
        Raises an exception if the connection fails.
        """
        if self.client is not None:
            logger.warning("Connection attempt ignored, MongoDB client already initialized.")
            return

        if not self.mongodb_url or not self.mongodb_db_name:
             logger.error("MONGODB_URL or MONGODB_DB not configured in settings.")
             # Raise configuration error instead of letting it fail later?
             raise ValueError("MongoDB connection details missing in settings.")

        try:
            logger.info(f"Attempting to connect to MongoDB at {self.mongodb_url}...")
            # Configure timeouts from settings if available, otherwise use defaults
            connect_timeout = getattr(settings, 'MONGODB_CONNECT_TIMEOUT_MS', 5000)
            server_select_timeout = getattr(settings, 'MONGODB_SERVER_SELECTION_TIMEOUT_MS', 5000)

            self.client = AsyncIOMotorClient(
                self.mongodb_url,
                serverSelectionTimeoutMS=server_select_timeout,
                connectTimeoutMS=connect_timeout,
                # socketTimeoutMS is often less critical here, but can be added
            )
            # The 'ping' command is cheap and verifies connectivity + authentication
            await self.client.admin.command('ping')
            # Assign database instance *after* successful ping
            self.db = self.client[self.mongodb_db_name]
            logger.info(f"MongoDB connection successful. Database '{self.mongodb_db_name}' is ready.")

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
            # Ensure client/db are reset on failure
            self.client = None
            self.db = None
            # Re-raise the exception so the application lifespan knows connection failed
            raise

    async def close(self):
        """Closes the MongoDB connection and resets client/db attributes."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed.")
        else:
            logger.info("No active MongoDB connection to close.")

    def get_db(self) -> AsyncIOMotorDatabase:
        """
        Returns the database instance.

        Raises:
            RuntimeError: If the database is not connected (self.db is None).
                          This typically means `connect()` failed or wasn't called.
        """
        if self.db is None:
            # This check correctly ensures connect() was called and succeeded.
            logger.critical("get_db called but database is not connected/initialized.")
            raise RuntimeError("Database not connected. Ensure connect() was called and succeeded during application startup.")
        return self.db

# Create a single, globally available instance of the MongoDB manager
mongodb = MongoDB()