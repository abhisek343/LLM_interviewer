# llm_managment_system2/server/app/core/config.py

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, EmailStr # Import EmailStr for validation
from typing import Optional, List # Use List for type hint consistency
from functools import lru_cache

class Settings(BaseSettings):
    # MongoDB settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "llm_interview_db"

    # JWT settings
    JWT_SECRET_KEY: str = "your-secret-key-here"  # Change this in production
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS settings
    # Pydantic-settings can parse JSON strings in .env into lists
    CORS_ORIGINS: List[str] = ["http://localhost:5173"] # Remember to verify this port

    # Gemini API settings
    GEMINI_API_KEY: str = "your-gemini-api-key"  # Add your Gemini API key

    # Default Admin Credentials
    DEFAULT_ADMIN_EMAIL: Optional[EmailStr] = None
    DEFAULT_ADMIN_USERNAME: Optional[str] = None
    DEFAULT_ADMIN_PASSWORD: Optional[str] = None

    # Pydantic v2 model configuration
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

@lru_cache()
def get_settings():
    return Settings()

# --- UNCOMMENT THE LINE BELOW ---
# Create an instance for direct import by other modules if needed.
settings = get_settings()
# --- END OF CHANGE ---