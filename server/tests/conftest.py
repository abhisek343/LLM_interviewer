import os
import sys
import pytest
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from app.db.mongodb import mongodb

# Add the server directory to Python path
server_dir = Path(__file__).parent.parent
sys.path.append(str(server_dir))

# Set environment variables for testing
os.environ["MONGODB_URL"] = "mongodb://localhost:27017"
os.environ["DATABASE_NAME"] = "llminterview"
os.environ["JWT_SECRET_KEY"] = "test_secret_key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["GEMINI_API_KEY"] = "test_api_key"

@pytest.fixture(autouse=True)
async def setup_mongodb():
    # Initialize MongoDB connection
    mongodb.client = AsyncIOMotorClient(os.environ["MONGODB_URL"])
    mongodb.client.get_database(os.environ["DATABASE_NAME"])
    
    # Clear test database before each test
    await mongodb.client.drop_database(os.environ["DATABASE_NAME"])
    
    yield
    
    # Clear test database and close connection after each test
    await mongodb.client.drop_database(os.environ["DATABASE_NAME"])
    mongodb.client.close() 