# LLM_interviewer/server/app/core/security.py

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorDatabase

# Assuming UserOut schema is correctly defined here based on previous step
from app.schemas.user import UserOut, TokenData # Added TokenData import potentially needed
from app.core.config import settings # Use settings instance directly
from app.db.mongodb import mongodb # Import mongodb instance

# --- Configuration ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# Define the scheme instance here - more self-contained
# Ensure the tokenUrl matches the path to your login endpoint *relative* to the base URL
# If your login route is mounted at /api/v1/auth/login, this might need adjustment depending
# on how TestClient interacts with it vs how browser does. For direct API calls, '/auth/login'
# might be correct if the prefix is handled by the client/base URL. Let's stick to the original.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login") # Relative path

# --- Database Dependency ---
async def get_db() -> AsyncIOMotorDatabase:
    """
    Dependency that returns the database instance.
    This can be overridden in tests to provide a test database.
    """
    return mongodb.get_db()

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
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

# --- Core User Fetching Dependency ---
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> UserOut:
    """
    Decodes JWT token, fetches user from DB, validates, and returns UserOut model.
    This is the primary dependency for getting the user associated with a token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email: Optional[str] = payload.get("sub")
        # Optional: Extract role or user_id if needed for validation right away
        # role: Optional[str] = payload.get("role")
        # user_id: Optional[str] = payload.get("id")

        if email is None:
            logger.warning("Token payload missing 'sub' (email).")
            raise credentials_exception

        token_data = TokenData(email=email) # Can add role/id here if needed

    except JWTError as e:
        logger.warning(f"JWT Error decoding token: {e}")
        raise credentials_exception
    except Exception as e: # Catch potential errors during payload processing
        logger.error(f"Error processing token payload: {e}", exc_info=True)
        raise credentials_exception

    try:
        user_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one({"email": token_data.email})

        if user_doc is None:
            logger.warning(f"User associated with token email '{token_data.email}' not found in DB.")
            raise credentials_exception

        # Ensure the user document has an _id before validation
        if "_id" not in user_doc:
            logger.error(f"User document for email '{token_data.email}' is missing '_id'.")
            raise HTTPException(status_code=500, detail="User data integrity issue.")

        # Validate user data against UserOut schema before returning
        # model_validate handles the alias mapping automatically (_id -> id)
        return UserOut.model_validate(user_doc)

    except HTTPException:
        raise # Re-raise HTTPExceptions directly (like 401, 500 from above)
    except Exception as e:
        logger.error(f"Unexpected error fetching/validating user from DB: {e}", exc_info=True)
        # Return a generic 500 for unexpected DB or validation issues
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while validating the user."
        )

# --- Active User Dependency (Optional Wrapper) ---
async def get_current_active_user(current_user: UserOut = Depends(get_current_user)) -> UserOut:
    """
    A wrapper dependency that first gets the current user,
    and could potentially add checks (e.g., is_active flag).
    Currently, it just returns the user fetched by get_current_user.
    """
    # Example: Add future checks here if needed
    # if not current_user.is_active: # Assuming an 'is_active' field exists
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Deprecated function, keep if needed for reference or specific use cases
def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None