# llm_managment_system2/server/app/main.py

from fastapi import FastAPI, Request, status # Added Request, status
from fastapi.exceptions import RequestValidationError # Added RequestValidationError
from fastapi.responses import JSONResponse # Added JSONResponse (optional if you customize response)
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, interview
from app.db.mongodb import mongodb
from app.core.config import get_settings
import logging # Added logging
from datetime import datetime # Ensure datetime is imported if used in seeding
# Import security utils if needed for seeding
from app.core.security import get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


settings = get_settings()

app = FastAPI(
    title="LLM Interview System",
    description="API for managing technical interviews with LLM-powered question generation",
    version="1.0.0"
)

# --- Add the Exception Handler Here ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handles Pydantic validation errors globally.
    Logs the detailed error and re-raises to let FastAPI generate the default 422 response.
    """
    # Log the detailed validation errors on the server side for debugging
    # exc.errors() provides a list of dicts with error details
    # exc.body might contain the raw request body if needed
    error_details = exc.errors()
    logger.warning(f"Validation error for request {request.method} {request.url}: {error_details}")
    # logger.debug(f"Request body causing validation error: {exc.body}") # Uncomment for more debugging

    # Option 1 (Recommended): Re-raise to use FastAPI's default 422 response format
    # This is usually best as the client-side code was adapted to handle this format.
    raise exc

    # Option 2: Return a custom JSON response (Uncomment below and comment out 'raise exc' if needed)
    # return JSONResponse(
    #     status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    #     # You can customize the content structure here if necessary
    #     content={"detail": error_details}
    # )
# --- End of Exception Handler ---


# --- Optional: Function to Seed Default Admin ---
async def seed_default_admin():
    """Checks for and creates the default admin user if they don't exist."""
    try:
        db = mongodb.get_db() # Make sure mongodb is connected

        # Safely get settings from .env, provide fallbacks if necessary
        admin_email = getattr(settings, 'DEFAULT_ADMIN_EMAIL', None)
        admin_username = getattr(settings, 'DEFAULT_ADMIN_USERNAME', None)
        admin_password = getattr(settings, 'DEFAULT_ADMIN_PASSWORD', None)

        if not all([admin_email, admin_username, admin_password]):
            logger.warning("Default admin credentials not fully configured in .env. Skipping admin seeding.")
            return

        existing_admin = await db.users.find_one({"email": admin_email})

        if not existing_admin:
            logger.info(f"Default admin user '{admin_email}' not found. Creating...")
            hashed_password = get_password_hash(admin_password)
            admin_doc = {
                "username": admin_username,
                "email": admin_email,
                "hashed_password": hashed_password,
                "role": "admin", # Explicitly set role
                "created_at": datetime.utcnow()
            }
            await db.users.insert_one(admin_doc)
            logger.info(f"Default admin user '{admin_email}' created successfully.")
        else:
            logger.info(f"Default admin user '{admin_email}' already exists.")
    except Exception as e:
        logger.error(f"Error during admin user seeding: {e}", exc_info=True)

# --- End of Admin Seeding Function ---


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS, # Use specific origins from settings in production is safer
    # allow_origins=["*"], # Use "*" for broad development access if needed, but less secure
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Ensure the prefix is defined within the router files (auth.py, interview.py)
# e.g., router = APIRouter(prefix="/auth", tags=["auth"])
app.include_router(auth.router)
app.include_router(interview.router)

@app.on_event("startup")
async def startup_db_client():
    logger.info("Application startup: Connecting to MongoDB...")
    await mongodb.connect()
    logger.info("Application startup: MongoDB connected.")
    # --- Seed the default admin user on startup ---
    # Note: Running this on every startup might have slight overhead.
    # Running a separate seeding script once is often preferred for production.
    await seed_default_admin()
    # ---

@app.on_event("shutdown")
async def shutdown_db_client():
    logger.info("Application shutdown: Closing MongoDB connection...")
    await mongodb.close()
    logger.info("Application shutdown: MongoDB connection closed.")

@app.get("/")
async def root():
    """
    Root endpoint for the API.
    """
    return {"message": "Welcome to LLM Interview System API"}