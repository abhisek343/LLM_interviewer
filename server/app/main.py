# LLM_interviewer/server/app/main.py

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import settings and database connection
from app.core.config import settings
from app.db.mongodb import mongodb

# Import API routers
from app.api.routes import auth, candidates, interview, admin

# Import seeding functions (ensure these paths are correct)
# Assuming seed_admin_user might be in a separate file like seed_data.py
# Adjust the import path if your structure is different
try:
    from app.db.seed_data import seed_admin_user
except ImportError:
    # Define a dummy function if seed_data doesn't exist or is optional
    async def seed_admin_user():
        logging.warning("seed_admin_user function not found or import failed.")
        pass # Do nothing if not found

from app.db.seed_default_questions import seed_default_questions


# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    logger.info("Application startup...")
    try:
        await mongodb.connect()
        # Call seeding functions after successful connection
        await seed_admin_user()
        await seed_default_questions()
        yield
    except Exception as e:
        logger.critical(f"FATAL: Failed to connect to MongoDB or seed data during startup: {e}", exc_info=True)
        raise
    finally:
        logger.info("Application shutdown...")
        await mongodb.close()

# --- FastAPI App Initialization ---
# Correctly define the 'app' instance here
app = FastAPI(
    title=settings.APP_NAME,
    openapi_url="/openapi.json", # Standard location
    lifespan=lifespan
)


# --- Middleware Setup ---
# Add CORS middleware using settings
if settings.CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS, # Use parsed list from settings
        allow_credentials=True,
        allow_methods=["*"], # Allow all standard methods
        allow_headers=["*"], # Allow all headers
    )
    logger.info(f"CORS enabled for origins: {settings.CORS_ALLOWED_ORIGINS}")
else:
     logger.warning("CORS_ALLOWED_ORIGINS not set. CORS middleware not added.")


# --- Include API Routers ---
app.include_router(auth.router, prefix="/api/v1")
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(interview.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
logger.info("Included API routers.")

# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    """A simple endpoint to confirm the API is running."""
    return {"message": f"Welcome to the {settings.APP_NAME} API"}

# Note: No TestClient should be instantiated here.
# TestClient is for use within test files only.