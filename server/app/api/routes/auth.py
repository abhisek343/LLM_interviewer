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
# Ensure correct schemas are imported
from app.schemas.user import UserCreate, UserOut, Token, TokenData, UserRole
from app.db.mongodb import mongodb # Import the mongodb instance
from app.core.config import settings # Import settings instance directly
# UserRole was moved to schemas, so importing from there is correct
# from app.models.user import UserRole # Redundant if imported from schemas
import logging

# Logger setup
logger = logging.getLogger(__name__)

# Router setup - prefix and tags match original file
router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Register Endpoint ---
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    """Registers a new user (candidate, hr, or admin)."""
    # Pydantic validation handles role check based on UserRole Literal in UserCreate schema

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
        # Ensure we use .model_dump() for Pydantic v2
        user_doc = user.model_dump(exclude={"password"})
        user_doc["hashed_password"] = hashed_password
        user_doc["created_at"] = datetime.utcnow()
        # Ensure all required fields from the User model are present or handled
        user_doc.setdefault("updated_at", user_doc["created_at"])
        user_doc.setdefault("resume_path", None)
        user_doc.setdefault("resume_text", None)

        # Insert user into database
        result = await db[settings.MONGODB_COLLECTION_USERS].insert_one(user_doc)
        # Fetch using the inserted_id which is an ObjectId
        created_user_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": result.inserted_id})

        if not created_user_doc:
            logger.error(f"Failed to retrieve created user after insert for email: {user.email}")
            raise HTTPException(status_code=500, detail="Failed to create user account.")

        logger.info(f"User '{user.username}' ({user.email}) registered successfully as '{user.role}'.")
        # Use model_validate for Pydantic V2 validation
        return UserOut.model_validate(created_user_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during user registration for {user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration."
        )


# --- Login Endpoint (MODIFIED) ---
@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Logs in a user using email OR username and returns an access token."""
    try:
        db = mongodb.get_db()
        identifier = form_data.username # Input can be email or username

        # --- MODIFIED DB LOOKUP: Use $or to check email OR username ---
        user_from_db = await db[settings.MONGODB_COLLECTION_USERS].find_one({
            "$or": [
                {"email": identifier},
                {"username": identifier}
            ]
        })
        # --- END MODIFIED DB LOOKUP ---

        # Check if user exists and password is correct
        if not user_from_db or not verify_password(form_data.password, user_from_db.get("hashed_password", "")):
            logger.warning(f"Login attempt failed for identifier: {identifier} (User not found or incorrect password)")
            # --- MODIFIED ERROR DETAIL MESSAGE ---
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect login credentials. Please provide a valid username or email ID and password.", # Specific message
                headers={"WWW-Authenticate": "Bearer"},
            )
        # --- END MODIFIED ERROR DETAIL MESSAGE ---

        # Ensure email exists in the retrieved document before using it
        user_email_for_token = user_from_db.get("email")
        if not user_email_for_token:
             logger.error(f"User document found for identifier '{identifier}' is missing the 'email' field. Cannot generate token.")
             raise HTTPException(
                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail="User data integrity issue. Cannot complete login."
             )

        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user_email_for_token, # Use the confirmed email as subject
                "role": user_from_db.get("role"), # Ensure role exists
                # "id": str(user_from_db["_id"]) # Optional: Include stringified user ID
                },
            expires_delta=access_token_expires
        )

        logger.info(f"Successful login for user identified by: {identifier} (Email: {user_email_for_token})")
        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        # Re-raise specific HTTP exceptions (like the 401 or 500 above)
        raise
    except Exception as e:
        # Catch any other unexpected errors during the process
        logger.error(f"Error during login for identifier {form_data.username}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login."
        )


# --- Get Current User Endpoint ---
# This endpoint relies on the dependency from security.py
@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: UserOut = Depends(get_current_active_user)):
    """
    Returns the details of the currently authenticated user.
    The get_current_active_user dependency handles token verification and user fetching.
    """
    logger.info(f"Fetching profile for current user: {current_user.username}")
    # The dependency already returns a validated UserOut model
    return current_user