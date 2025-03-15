# LLM_interviewer/server/app/core/config.py

import logging
import os # <-- Added import
from functools import lru_cache
# Import Dict for the updated type hint
from typing import List, Optional, Union, Any, Dict

# Import Pydantic v2 components
from pydantic import EmailStr, field_validator, ValidationInfo, ConfigDict
from pydantic_settings import BaseSettings
# Import google-generativeai types for better type hinting where possible
import google.generativeai as genai
# Keep SafetySettingDict import commented or remove if not used directly as hint
# from google.generativeai.types import GenerationConfigDict, SafetySettingDict
from google.generativeai.types import GenerationConfigDict # Still use for GenerationConfig

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__) # Ensure logger is defined at module level

# --- ADDED DEBUG BLOCK (Checks raw environment variable) ---
env_key_value = os.getenv('GEMINI_API_KEY')
if env_key_value:
    log_env_key_display = f"{env_key_value[:5]}...{env_key_value[-4:]}"
else:
    log_env_key_display = "NOT SET in os.environ"
logger.info(f"--- DEBUG: Value of os.getenv('GEMINI_API_KEY') before Settings init: {log_env_key_display} ---")
# --- END DEBUG BLOCK ---

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    Uses Pydantic v2 features.
    """
    # --- App Configuration ---
    APP_NAME: str = "LLM Interviewer API"
    API_V1_STR: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    TESTING_MODE: bool = False
    # --- Database Configuration ---
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "llm_interviewer_db"
    MONGODB_COLLECTION_USERS: str = "users"
    MONGODB_COLLECTION_INTERVIEWS: str = "interviews"
    MONGODB_COLLECTION_QUESTIONS: str = "questions"
    MONGODB_COLLECTION_RESPONSES: str = "responses"
    MONGODB_COLLECTION_HR_MAPPING_REQUESTS: str = "hr_mapping_requests"
    MONGODB_COLLECTION_MESSAGES: str = "messages"

    # --- Security Configuration ---
    JWT_SECRET_KEY: str = "your_super_secret_key_please_change"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # --- CORS Configuration ---
    CORS_ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Default Admin User (Optional) ---
    DEFAULT_ADMIN_EMAIL: Optional[EmailStr] = "admin@example.com"
    DEFAULT_ADMIN_USERNAME: Optional[str] = "adminuser"
    DEFAULT_ADMIN_PASSWORD: Optional[str] = "adminpassword"

    # --- File Uploads ---
    UPLOAD_DIR: str = "uploads"
    RESUME_SUBDIR: str = "resumes"
    ALLOWED_RESUME_EXTENSIONS: List[str] = ["pdf", "docx"]
    MAX_RESUME_SIZE_MB: int = 5

    # --- Gemini Configuration ---
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL_NAME: str = "gemini-1.5-flash-latest" # Note: Log showed gemini-1.5-pro, ensure this matches intended model

    # Still use GenerationConfigDict for this one if validation works
    GEMINI_GENERATION_CONFIG: GenerationConfigDict = {
         "temperature": 0.7, "top_p": 1.0, "top_k": 1, "max_output_tokens": 2048
    }

    # *** CHANGE THE TYPE HINT HERE ***
    # Change from List[SafetySettingDict] to List[Dict[str, str]]
    # This avoids Pydantic's strict enum validation based on the specific type hint,
    # but keeps the structure correct for the google-generativeai library later.
    GEMINI_SAFETY_SETTINGS: List[Dict[str, str]] = [
         {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
         {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
         {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
         {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    # --- Pydantic V2 Field Validators ---
    @field_validator('CORS_ALLOWED_ORIGINS', mode='before')
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith('['):
            return [i.strip() for i in v.split(',') if i.strip()]
        elif isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]
        return v

    @field_validator('ALLOWED_RESUME_EXTENSIONS', mode='before')
    @classmethod
    def assemble_allowed_extensions(cls, v: Any) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith('['):
            return [i.strip().lower() for i in v.split(',') if i.strip()]
        elif isinstance(v, list):
            return [str(i).strip().lower() for i in v if str(i).strip()]
        return v

    # --- Pydantic V2 Model Configuration ---
    model_config = ConfigDict(
        case_sensitive=True,
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )

    # --- Hash Method for LRU Cache Compatibility ---
    def __hash__(self):
        return hash((
            self.APP_NAME, self.MONGODB_URL, self.MONGODB_DB, self.API_V1_STR,
            self.JWT_SECRET_KEY, self.JWT_ALGORITHM, self.GEMINI_MODEL_NAME
        ))


# Ensure cache is commented out for testing
# @lru_cache()
def get_settings() -> Settings:
    """Loads and returns the application settings."""
    # Modified log message slightly
    logger.info("Loading application settings (cache disabled)...")
    try:
        settings_instance = Settings()

        # --- ADDED DEBUG LINE (Checks value after Settings init) ---
        key_to_log = settings_instance.GEMINI_API_KEY
        log_key_display_settings = f"{key_to_log[:5]}...{key_to_log[-4:]}" if key_to_log else "None"
        logger.info(f"--- DEBUG: Settings() instance created. Key: {log_key_display_settings} ---")
        # --- END ADDED DEBUG LINE ---

        logger.info(f"Settings loaded for APP_NAME: {settings_instance.APP_NAME}")
        logger.info(f"MongoDB DB: {settings_instance.MONGODB_DB}")
        logger.info(f"CORS Origins: {settings_instance.CORS_ALLOWED_ORIGINS}")
        logger.info(f"Gemini Model: {settings_instance.GEMINI_MODEL_NAME}")
        logger.info(f"Gemini Key Set: {'Yes' if settings_instance.GEMINI_API_KEY else 'No'}")
        # Log the safety settings structure (without values if sensitive)
        logger.info(f"Gemini Safety Settings applied: {len(settings_instance.GEMINI_SAFETY_SETTINGS)} rules")
        return settings_instance
    except Exception as e:
        logger.critical(f"FATAL: Failed to load settings: {e}", exc_info=True)
        raise SystemExit(f"Could not load settings: {e}")


# Create a single settings instance for the application to import
settings = get_settings()
