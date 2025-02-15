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
# --- ADD hr to imports ---
from app.api.routes import auth, candidates, interview, admin, hr

# --- Seeding Function Import (Consolidated) ---
# (No changes needed here)
try:
    from app.db.seed_data import seed_all_data
    SEEDING_AVAILABLE = True
    logging.info("Successfully imported seed_all_data from app.db.seed_data.")
except ImportError:
    async def seed_all_data(): # Define a dummy async function if import fails
        logging.warning("Consolidated seed_all_data function not found in app.db.seed_data or import failed. Seeding will be skipped.")
    SEEDING_AVAILABLE = False


# --- Logging Setup ---
# (No changes needed here)
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# --- Application Lifespan ---
# (No changes needed here)
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Handles application startup and shutdown events.
    Connects to database, runs consolidated seeding (if available), and ensures disconnection.
    """
    logger.info("Application startup sequence initiated...")
    db_connected = False
    try:
        logger.info("Attempting to connect to MongoDB...")
        await mongodb.connect()
        db_connected = True
        logger.info("MongoDB connection successful.")

        if SEEDING_AVAILABLE and not settings.TESTING_MODE:
            logger.info("Attempting to run consolidated database seeding...")
            await seed_all_data()
        elif settings.TESTING_MODE:
            logger.info("TESTING_MODE enabled, skipping application lifespan seeding.")
        else:
            logger.warning("Database seeding skipped (function not available).")

        logger.info("Application startup complete.")
        yield # Application runs here

    except Exception as e:
        logger.critical(f"FATAL: Application startup failed: {e}", exc_info=True)
    finally:
        logger.info("Application shutdown sequence initiated...")
        if db_connected:
            await mongodb.close()
            logger.info("MongoDB connection closed.")
        else:
            logger.warning("Skipping MongoDB close sequence as connection was not established.")
        logger.info("Application shutdown complete.")


# --- FastAPI App Initialization ---
# (No changes needed here)
app = FastAPI(
    title=settings.APP_NAME,
    description="API for the LLM Interviewer platform.",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)


# --- Middleware Setup ---
# (No changes needed here)
if settings.CORS_ALLOWED_ORIGINS:
    allowed_origins = [str(origin).strip() for origin in settings.CORS_ALLOWED_ORIGINS]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS middleware enabled for origins: {allowed_origins}")
else:
    logger.warning("CORS_ALLOWED_ORIGINS is not set in settings. CORS middleware not added.")


# --- API Router Inclusion ---
# Include routers from the api module with the defined prefix
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["Authentication"])
app.include_router(candidates.router, prefix=settings.API_V1_STR, tags=["Candidates"])
app.include_router(interview.router, prefix=settings.API_V1_STR, tags=["Interviews"])
app.include_router(admin.router, prefix=settings.API_V1_STR, tags=["Admin"])
# --- ADD the new HR router ---
app.include_router(hr.router, prefix=settings.API_V1_STR, tags=["HR"])
# --- Update Log Message ---
logger.info(f"Included API routers (Auth, Candidates, Interviews, Admin, HR) under prefix: {settings.API_V1_STR}")


# --- Root Endpoint ---
# (No changes needed here)
@app.get("/", tags=["Root"])
async def read_root() -> dict[str, str]:
    """A simple root endpoint to confirm the API is running."""
    return {"message": f"Welcome to the {settings.APP_NAME} API"}

# Health check endpoint (useful for monitoring)
@app.get("/health", tags=["Health Check"])
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}