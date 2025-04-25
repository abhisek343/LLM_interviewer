# LLM_interviewer/server/app/core/config.py

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, EmailStr, validator, Field # Added validator, Field
from typing import Optional, List, Union # Added Union
from functools import lru_cache
import json # For parsing list from env var

class Settings(BaseSettings):
    # --- Core App Settings ---
    APP_NAME: str = "LLM Interviewer"
    DEBUG: bool = False

    # --- MongoDB Settings ---
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "llm_interview_db"
    # Collection Names
    MONGODB_COLLECTION_USERS: str = "users"
    MONGODB_COLLECTION_INTERVIEWS: str = "interviews"
    MONGODB_COLLECTION_RESPONSES: str = "responses"
    MONGODB_COLLECTION_QUESTIONS: str = "questions" # For default questions

    # --- JWT Settings ---
    JWT_SECRET_KEY: str = "your_strong_secret_key_change_this" # ** CHANGE THIS IN PRODUCTION **
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 # Increased expiry slightly

    # --- CORS Settings ---
    # Allow origins from env var (comma-separated) or defaults
    CORS_ALLOWED_ORIGINS_STR: Optional[str] = None # Env var name: CORS_ALLOWED_ORIGINS_STR
    CORS_ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @validator('CORS_ALLOWED_ORIGINS', pre=True, always=True)
    def assemble_cors_origins(cls, v, values):
        # If CORS_ALLOWED_ORIGINS_STR is set in env, parse it
        if values.get('CORS_ALLOWED_ORIGINS_STR'):
            # Split by comma, strip whitespace, filter empty
            origins = [origin.strip() for origin in values['CORS_ALLOWED_ORIGINS_STR'].split(',') if origin.strip()]
            if origins:
                return origins
        # Otherwise, return the default list v
        return v

    # --- Gemini API Settings ---
    GEMINI_API_KEY: Optional[str] = None # Should be set in .env
    GEMINI_MODEL_NAME: str = "gemini-1.5-flash" # Changed to a newer recommended model

    # --- File Upload Settings ---
    RESUME_UPLOAD_DIR: str = "uploads/resumes"
    # Allowed extensions can be a JSON string in .env (e.g., '["pdf", "docx"]')
    ALLOWED_RESUME_EXTENSIONS_JSON: Optional[str] = None # Env var name: ALLOWED_RESUME_EXTENSIONS_JSON
    ALLOWED_RESUME_EXTENSIONS: List[str] = [".pdf", ".docx"] # Default

    @validator('ALLOWED_RESUME_EXTENSIONS', pre=True, always=True)
    def assemble_allowed_extensions(cls, v, values):
        if values.get('ALLOWED_RESUME_EXTENSIONS_JSON'):
            try:
                extensions = json.loads(values['ALLOWED_RESUME_EXTENSIONS_JSON'])
                # Ensure they start with a dot
                return [f".{ext.lstrip('.').lower()}" for ext in extensions if isinstance(ext, str)]
            except json.JSONDecodeError:
                # Handle error or use default
                pass # Falls through to return default v
        # Ensure default starts with dot and is lowercase
        return [f".{ext.lstrip('.').lower()}" for ext in v]


    # --- Evaluation Settings ---
    EVALUATION_SCORE_MIN: float = 0.0
    EVALUATION_SCORE_MAX: float = 5.0

    # --- Default Admin Credentials ---
    DEFAULT_ADMIN_EMAIL: Optional[EmailStr] = None
    DEFAULT_ADMIN_USERNAME: Optional[str] = None
    DEFAULT_ADMIN_PASSWORD: Optional[str] = None


    # --- Pydantic Model Configuration ---
    model_config = ConfigDict(
        env_file=".env",          # Load .env file
        env_file_encoding="utf-8",
        extra="ignore",           # Ignore extra fields from env
        case_sensitive=False      # Env var names are case-insensitive usually
    )

@lru_cache()
def get_settings():
    """Returns the cached settings instance."""
    return Settings()

# Create an instance for direct import by other modules
settings = get_settings()

# Log loaded settings (optional, be careful with secrets)
# import logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)
# logger.info("Settings loaded:")
# logger.info(f"  DB: {settings.MONGODB_DB} on {settings.MONGODB_URL}")
# logger.info(f"  CORS Origins: {settings.CORS_ALLOWED_ORIGINS}")
# logger.info(f"  Gemini Model: {settings.GEMINI_MODEL_NAME}")
# logger.info(f"  Resume Dir: {settings.RESUME_UPLOAD_DIR}")
# logger.info(f"  Allowed Extensions: {settings.ALLOWED_RESUME_EXTENSIONS}")