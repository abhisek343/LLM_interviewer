# llm_managment_system2/server/app/db/mongodb.py

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings # Assuming settings are correctly loaded
import logging
from urllib.parse import urlparse
import asyncio

logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None
        # Use settings directly for configuration
        self.mongodb_url = settings.MONGODB_URL
        self.mongodb_db_name = settings.MONGODB_DB

    async def connect(self):
        """Connect to MongoDB."""
        if self.client is None:
            try:
                logger.info(f"Attempting to connect to MongoDB at {self.mongodb_url}")
                self.client = AsyncIOMotorClient(
                    self.mongodb_url,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=5000
                )
                # Force connection and check if it's successful
                await self.client.admin.command('ping')
                self.db = self.client[self.mongodb_db_name]
                logger.info(f"Successfully obtained database handle for: {self.mongodb_db_name}")
                logger.info("MongoDB connection successful (ping successful).")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                self.client = None
                self.db = None
                raise

    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed.")

    def get_db(self) -> AsyncIOMotorDatabase:
        """Get database instance."""
        if self.db is None:
            raise RuntimeError("Database not connected. Ensure connect() was called and succeeded.")
        return self.db

# Create a single instance
mongodb = MongoDB()