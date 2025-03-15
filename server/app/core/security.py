# LLM_interviewer/server/app/core/security.py

import logging
from datetime import datetime, timedelta, timezone # Use timezone-aware UTC
from typing import Optional, Annotated # Use Annotated for Depends clarity

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClient # Added AsyncIOMotorClient
from pydantic import ValidationError # For catching Pydantic validation errors
from bson import ObjectId # Import ObjectId for checking _id

# Import schemas and configuration
from app.schemas.user import UserOut, TokenData
from app.core.config import settings
from app.db.mongodb import mongodb # Import the singleton instance

# --- Configuration ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# Define the OAuth2 scheme instance
# tokenUrl should point to your login endpoint's path relative to the base URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# --- Database Dependency ---
async def get_db() -> AsyncIOMotorDatabase:
    """
    Dependency that returns the database instance from the mongodb singleton.
    This confirms the correct usage: depending on this function provides the DB handle.
    """
    try:
        # Get the database instance using the singleton's method
        db_instance = mongodb.get_db()
        # --- Add check if DB is available ---
        if db_instance is None:
            logger.critical("get_db dependency called, but mongodb.get_db() returned None!")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not available (singleton returned None)."
            )
        # --- End check ---
        # --- Optional: Ping DB here to ensure connection is live ---
        # try:
        #     await db_instance.command('ping')
        # except Exception as ping_e:
        #     logger.error(f"Database ping failed in get_db dependency: {ping_e}", exc_info=True)
        #     raise HTTPException(
        #         status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        #         detail="Database connection validation failed."
        #     )
        # --- End optional ping ---
        return db_instance
    except RuntimeError as e:
        # If mongodb.get_db() raises RuntimeError (not connected), re-raise as HTTPException
        logger.error(f"Database connection error in get_db dependency: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available (RuntimeError)."
        )
    # --- Add catch for the specific HTTPException raised above ---
    except HTTPException:
        raise
    # --- End catch ---
    except Exception as e:
         logger.error(f"Unexpected error in get_db dependency: {e}", exc_info=True)
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error getting database connection."
         )


# Type alias for dependency injection clarity
CurrentDB = Annotated[AsyncIOMotorDatabase, Depends(get_db)]
Token = Annotated[str, Depends(oauth2_scheme)]

# --- Password Utilities ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

# --- JWT Token Utilities ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        # Use timezone.utc for consistency
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

# --- Core User Fetching Dependency ---
async def get_current_user(token: Token, db: CurrentDB) -> UserOut:
    """
    Decodes JWT token, fetches user from DB, validates, and returns UserOut model.
    Handles token errors (401), user not found (401), and DB/validation errors (500).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    internal_server_exception = HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An internal error occurred while validating the user.",
    )

    # 1. Decode Token
    email: Optional[str] = None # Initialize email
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email = payload.get("sub") # Assign email here
        logger.debug(f"[AUTH_DEBUG] Decoded token for email: {email}") # Log decoded email
        if email is None:
            logger.warning("Token payload missing 'sub' (email).")
            raise credentials_exception
    except JWTError as e:
        logger.warning(f"JWT Error decoding token: {e}")
        raise credentials_exception
    except Exception as e: # Catch potential errors during payload processing
        logger.error(f"Unexpected error processing token payload: {e}", exc_info=True)
        raise credentials_exception # Treat unexpected token processing errors as auth failure

    # 2. Fetch and Validate User from DB
    if email: # Only proceed if email was decoded
        try:
            logger.debug(f"[AUTH_DEBUG] Attempting DB lookup for email: {email}")
            user_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one({"email": email})

            if user_doc is None:
                logger.warning(f"[AUTH_DEBUG] User NOT FOUND in DB for email: {email}")
                raise credentials_exception
            else:
                # --- ADDED: Log fetched user details BEFORE validation ---
                found_user_id = user_doc.get('_id')
                found_username = user_doc.get('username')
                logger.info(f"[AUTH_DEBUG] User FOUND in DB for email: {email}. Fetched _id: {found_user_id}, Fetched username: {found_username}")
                # --- END ADDED LOG ---

                # Ensure the user document has an _id before validation
                if "_id" not in user_doc or not isinstance(found_user_id, ObjectId): # Check type too
                    logger.error(f"User document for email '{email}' is missing '_id' or it's not an ObjectId. Potential data integrity issue. Doc: {user_doc}")
                    # Treat data integrity issues as internal server errors
                    raise internal_server_exception

                # Validate database data against the UserOut schema
                # This ensures the data structure is correct before returning
                try:
                    user = UserOut.model_validate(user_doc)
                    logger.debug(f"[AUTH_DEBUG] Successfully validated user doc into UserOut model: {user.email} (Validated ID: {user.id}, Validated Username: {user.username})") # Log validated data
                    return user
                except ValidationError as e:
                    # Log the raw document that failed validation
                    logger.error(f"[AUTH_DEBUG] Pydantic validation failed for user '{email}' (DB ID: {found_user_id}). Error: {e}. Raw Doc: {user_doc}", exc_info=False) # Log less verbosely, include doc
                    raise internal_server_exception
        except HTTPException:
            # Re-raise HTTPExceptions directly (like 401 from above)
            raise
        except Exception as e:
            # Catch unexpected errors during DB lookup (e.g., network error, driver error)
            logger.error(f"Unexpected error fetching/validating user '{email}' from DB: {e}", exc_info=True)
            # Return a generic 500 for these unexpected issues
            raise internal_server_exception
    else:
        # This case should be handled by the email is None check earlier, but as safety
        logger.error("[AUTH_DEBUG] Cannot perform DB lookup - email is None after token decode.")
        raise credentials_exception


# --- Active User Dependency (Optional Wrapper) ---
# Use Annotated for the dependency for clarity
CurrentUser = Annotated[UserOut, Depends(get_current_user)]

async def get_current_active_user(current_user: CurrentUser) -> UserOut:
    """
    A wrapper dependency that first gets the current user.
    Can be extended to check for activity status if needed.
    """
    # Example: Add future checks here if needed
    # if not current_user.is_active: # Assuming an 'is_active' field exists in UserOut
    #     logger.warning(f"Attempt to access with inactive user: {current_user.email}")
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    logger.debug(f"get_current_active_user returning user: {current_user.email}") # Log success
    return current_user


# --- Role Verification Dependencies ---
async def verify_admin_user(current_user: CurrentUser) -> UserOut:
    """Dependency to ensure the current user has the 'admin' role."""
    if current_user.role != "admin":
        logger.warning(f"Admin access denied for user: {current_user.email} (Role: {current_user.role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires administrator privileges."
        )
    return current_user

async def verify_hr_or_admin_user(current_user: CurrentUser) -> UserOut:
    """Dependency to ensure the current user has 'hr' or 'admin' role."""
    if current_user.role not in ["hr", "admin"]:
        logger.warning(f"HR/Admin access denied for user: {current_user.email} (Role: {current_user.role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires HR or administrator privileges."
        )
    return current_user

async def require_candidate(current_user: CurrentUser) -> UserOut:
    """Dependency to ensure the current user has the 'candidate' role."""
    if current_user.role != "candidate":
        logger.warning(f"Candidate access denied for user: {current_user.email} (Role: {current_user.role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires candidate privileges."
        )
    return current_user