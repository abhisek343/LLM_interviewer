# LLM_interviewer/server/app/main.py

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import application components
from app.core.config import settings
from app.db.mongodb import mongodb # Import the singleton instance

# Import API routers
from app.api.routes import auth, candidates, interview, admin

# --- Seeding Function Import (Consolidated) ---
# Import the single seeding function from seed_data.py
try:
    from app.db.seed_data import seed_all_data
    SEEDING_AVAILABLE = True
    logging.info("Successfully imported seed_all_data from app.db.seed_data.")
except ImportError:
    async def seed_all_data(): # Define a dummy async function if import fails
        logging.warning("Consolidated seed_all_data function not found in app.db.seed_data or import failed. Seeding will be skipped.")
    SEEDING_AVAILABLE = False


# --- Logging Setup ---
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Handles application startup and shutdown events.
    Connects to database, runs consolidated seeding (if available), and ensures disconnection.
    """
    logger.info("Application startup sequence initiated...")
    db_connected = False
    try:
        # --- Startup ---
        logger.info("Attempting to connect to MongoDB...")
        await mongodb.connect() # Connect the singleton instance

        db_connected = True # Mark DB as connected *after* successful connection
        logger.info("MongoDB connection successful.")

        # --- Seeding (Run only if DB connection succeeded and function imported) ---
        if SEEDING_AVAILABLE and not settings.TESTING_MODE: # Check TESTING_MODE
            logger.info("Attempting to run consolidated database seeding...")
            await seed_all_data() # Single call to the consolidated function
            # Specific completion logs are now inside seed_all_data() and its internal functions
        elif settings.TESTING_MODE:
            logger.info("TESTING_MODE enabled, skipping application lifespan seeding.")
        else: # SEEDING_AVAILABLE is False
            logger.warning("Database seeding skipped (function not available).")

        logger.info("Application startup complete.")
        yield # Application runs here

    except Exception as e:
        # Log critical errors during startup, especially DB connection failure
        logger.critical(f"FATAL: Application startup failed: {e}", exc_info=True)
        # Optionally re-raise to prevent the app from starting in a broken state
        # raise
    finally:
        # --- Shutdown ---
        logger.info("Application shutdown sequence initiated...")
        if db_connected: # Only attempt to close if connection was established
            await mongodb.close()
            logger.info("MongoDB connection closed.")
        else:
            logger.warning("Skipping MongoDB close sequence as connection was not established.")
        logger.info("Application shutdown complete.")


# --- FastAPI App Initialization ---
app = FastAPI(
    title=settings.APP_NAME,
    description="API for the LLM Interviewer platform.",
    version="0.1.0", # Add a version number
    openapi_url=f"{settings.API_V1_STR}/openapi.json", # Use API prefix in docs URL
    docs_url=f"{settings.API_V1_STR}/docs", # Standard docs path
    redoc_url=f"{settings.API_V1_STR}/redoc", # Standard redoc path
    lifespan=lifespan # Register the lifespan context manager
)


# --- Middleware Setup ---
# Configure CORS (Cross-Origin Resource Sharing)
if settings.CORS_ALLOWED_ORIGINS:
    # Ensure CORS_ALLOWED_ORIGINS is a list of strings
    allowed_origins = [str(origin).strip() for origin in settings.CORS_ALLOWED_ORIGINS]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],  # Allows all standard methods (GET, POST, PUT, DELETE, etc.)
        allow_headers=["*"],  # Allows all headers
    )
    logger.info(f"CORS middleware enabled for origins: {allowed_origins}")
else:
    logger.warning("CORS_ALLOWED_ORIGINS is not set in settings. CORS middleware not added. This might block frontend requests.")


# --- API Router Inclusion ---
# Include routers from the api module with the defined prefix
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["Authentication"])
app.include_router(candidates.router, prefix=settings.API_V1_STR, tags=["Candidates"])
app.include_router(interview.router, prefix=settings.API_V1_STR, tags=["Interviews"])
app.include_router(admin.router, prefix=settings.API_V1_STR, tags=["Admin"])
logger.info(f"Included API routers under prefix: {settings.API_V1_STR}")


# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root() -> dict[str, str]:
    """A simple root endpoint to confirm the API is running."""
    return {"message": f"Welcome to the {settings.APP_NAME} API"}

# Health check endpoint (useful for monitoring)
@app.get("/health", tags=["Health Check"])
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}