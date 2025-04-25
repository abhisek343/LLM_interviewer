# LLM_interviewer/server/app/api/routes/auth.py

from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm # Keep this for /login route
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_active_user # Import the main dependency from security.py
)
from app.schemas.user import UserCreate, UserOut, Token, TokenData # Schemas are needed here
from app.db.mongodb import mongodb # Import the mongodb instance
from app.core.config import settings # Import settings instance directly
from app.models.user import UserRole # Import UserRole
import logging
from app.core.security import get_current_active_user # Or get_current_user if you prefer
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Logger setup
logger = logging.getLogger(__name__)


# --- Register Endpoint ---
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    """Registers a new user (candidate, hr, or admin)."""
    # Check if role is valid (Pydantic already does this via UserRole)
    # if user.role not in [UserRole.candidate, UserRole.hr, UserRole.admin]:
    #     raise HTTPException(status_code=400, detail="Invalid role specified")

    try:
        db = mongodb.get_db()
        # Check if email already exists
        existing_user_email = await db[settings.MONGODB_COLLECTION_USERS].find_one({"email": user.email})
        if existing_user_email:
            logger.warning(f"Registration attempt failed: Email '{user.email}' already exists.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered."
            )
        # Check if username already exists
        existing_user_username = await db[settings.MONGODB_COLLECTION_USERS].find_one({"username": user.username})
        if existing_user_username:
             logger.warning(f"Registration attempt failed: Username '{user.username}' already exists.")
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered."
             )

        # Create new user
        hashed_password = get_password_hash(user.password)
        user_doc = user.model_dump(exclude={"password"})
        user_doc["hashed_password"] = hashed_password
        user_doc["created_at"] = datetime.utcnow()

        # Insert user into database
        result = await db[settings.MONGODB_COLLECTION_USERS].insert_one(user_doc)
        created_user_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": result.inserted_id})

        if not created_user_doc:
            logger.error(f"Failed to retrieve created user after insert for email: {user.email}")
            raise HTTPException(status_code=500, detail="Failed to create user account.")

        logger.info(f"User '{user.username}' ({user.email}) registered successfully as '{user.role}'.")
        # Return the created user details using UserOut schema
        return UserOut.model_validate(created_user_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during user registration for {user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration."
        )


# --- Login Endpoint ---
@router.post("/login", response_model=Token) # Login returns a token
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Logs in a user and returns an access token."""
    try:
        db = mongodb.get_db()
        user_from_db = await db[settings.MONGODB_COLLECTION_USERS].find_one({"email": form_data.username}) # Use email as username for login

        if not user_from_db or not verify_password(form_data.password, user_from_db["hashed_password"]):
            logger.warning(f"Login attempt failed for email: {form_data.username} (User not found or incorrect password)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create access token including necessary details in payload
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user_from_db["email"],
                "role": user_from_db["role"],
                # Include user ID (as string) in token if needed by frontend/other services
                # "id": str(user_from_db["_id"])
                },
            expires_delta=access_token_expires
        )

        logger.info(f"Successful login for user {form_data.username}")
        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login for {form_data.username}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login."
        )


# --- Get Current User Endpoint ---
# This endpoint now relies on the dependency moved to security.py
@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: UserOut = Depends(get_current_active_user)):
    """
    Returns the details of the currently authenticated user.
    """
    logger.info(f"Fetching profile for current user: {current_user.username}")
    return current_user

# Note: The `get_current_user` function definition that was previously here has been moved to `security.py`.
# The `oauth2_scheme` is now defined and used within `security.py`.