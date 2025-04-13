# llm_managment_system2/server/app/db/mongodb.py

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings # Assuming settings are correctly loaded
import logging
from urllib.parse import urlparse

class MongoDB:
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None
        # Use settings directly for configuration
        self.mongodb_url = settings.MONGODB_URL
        self.mongodb_db_name = settings.MONGODB_DB

    async def connect(self):
        logging.info(f"Attempting to connect to MongoDB at {self.mongodb_url}")
        if self.client:
            logging.warning("Already connected to MongoDB.")
            return

        try:
            # Create client with timeout
            self.client = AsyncIOMotorClient(self.mongodb_url, serverSelectionTimeoutMS=5000)

            # Extract database name from URL or use setting
            parsed_url = urlparse(self.mongodb_url)
            db_name = parsed_url.path.lstrip('/')

            if not db_name:
                # Fallback to MONGODB_DB setting if no database in URL
                db_name = self.mongodb_db_name
                if not db_name:
                    raise ValueError("No database name specified in MONGODB_URL or MONGODB_DB setting")

            # Get database instance
            self.db = self.client[db_name]
            logging.info(f"Successfully obtained database handle for: {db_name}")

            # Verify connection by pinging the admin database
            await self.client.admin.command('ping')
            logging.info("MongoDB connection successful (ping successful).")

        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}", exc_info=True) # Add exc_info for detailed traceback
            if self.client:
                self.client.close()
            self.client = None
            self.db = None
            # Re-raise the exception so the application knows connection failed
            raise ConnectionError(f"Failed to connect to MongoDB: {e}") from e

    async def close(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logging.info("Closed MongoDB connection.")

    def get_db(self) -> AsyncIOMotorDatabase:
        # --- CORRECTED CHECK ---
        if self.db is None:
            raise RuntimeError("Database not connected. Ensure connect() was called and succeeded.")
        # --- END OF CORRECTION ---
        return self.db

# Create a single instance
mongodb = MongoDB()