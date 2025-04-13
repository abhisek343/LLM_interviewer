# llm_managment_system2/server/app/api/routes/auth.py

from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.core.security import verify_password, get_password_hash, create_access_token
from app.schemas.user import UserCreate, UserOut, Token, TokenData # Use schemas defined in schemas/user.py
from app.db.mongodb import mongodb # Import the mongodb instance
from app.core.config import get_settings
from typing import Optional
from jose import JWTError, jwt
import logging # Import logging

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
# Use relative path within the API, assuming base path handles prefix correctly
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login") # Simplified tokenUrl

# Logger setup
logger = logging.getLogger(__name__)

# --- Register Endpoint ---
# Changed response_model to UserOut if you want user details, or kept Token if only token is needed.
# Let's keep Token as per original intent, implies successful registration gives a login token.
@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    # Assuming mongodb.get_db() correctly returns the database object based on prior setup
    db = mongodb.get_database() # Using get_database() as defined in original mongodb.py
    if not db:
         logger.error("Failed to get database instance in /register")
         raise HTTPException(status_code=500, detail="Database connection not available.")

    # Check if user already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )

    try:
        # Create new user
        hashed_password = get_password_hash(user.password)
        user_doc = user.model_dump(exclude={"password"}) # Use model_dump for Pydantic v2
        user_doc["hashed_password"] = hashed_password
        user_doc["created_at"] = datetime.utcnow() # Fix for created_at validation

        # Insert user into database
        result = await db.users.insert_one(user_doc)

        # We need the user details to create the token payload
        created_user = await db.users.find_one({"_id": result.inserted_id})
        if not created_user:
            # This should ideally not happen if insert was successful
            logger.error(f"Failed to retrieve created user after insert for email: {user.email}")
            raise HTTPException(status_code=500, detail="Failed to retrieve created user.")

        # Validate the created user data (optional but good practice)
        # No need to convert _id to id here as UserOut doesn't use it
        try:
            user_for_token = UserOut.model_validate(created_user)
        except Exception as validation_error:
            logger.error(f"Failed to validate created user data: {validation_error}")
            raise HTTPException(status_code=500, detail="Failed processing created user data.")

        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_for_token.email, "role": user_for_token.role}, # Use data from validated user
            expires_delta=access_token_expires
        )

        # Return only the token, matching the Token response_model
        return {"access_token": access_token, "token_type": "bearer"}

    except Exception as e:
        # Log unexpected errors during registration process
        logger.error(f"Error during user registration for {user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration."
        )

# --- Login Endpoint ---
# Changed response_model to Token, assuming login returns token + user info
@router.post("/login", response_model=Token) # Kept Token, adjust if needed
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = mongodb.get_database() # Using get_database()
    if not db:
         logger.error("Failed to get database instance in /login")
         raise HTTPException(status_code=500, detail="Database connection not available.")

    # Note: OAuth2PasswordRequestForm uses 'username' field for the email
    user_from_db = await db.users.find_one({"email": form_data.username})

    if not user_from_db or not verify_password(form_data.password, user_from_db["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate against UserOut schema to get role etc. for token
    # No need to convert _id to id here
    try:
        user_out = UserOut.model_validate(user_from_db)
    except Exception as validation_error:
         logger.error(f"Failed to validate user data from DB during login for {form_data.username}: {validation_error}")
         raise HTTPException(status_code=500, detail="Failed processing user data.")


    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_out.email, "role": user_out.role},
        expires_delta=access_token_expires
    )

    # Return only the token, matching the Token response_model
    return {"access_token": access_token, "token_type": "bearer"}


# --- Dependency to get current user ---
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserOut:
    db = mongodb.get_database() # Using get_database()
    if not db:
         logger.error("Failed to get database instance in get_current_user")
         # Decide how to handle this - raise 500 or a specific auth error?
         # Raising 401 might mask DB issues but fits auth flow failure.
         raise HTTPException(status_code=503, detail="Database service unavailable.")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        email: Optional[str] = payload.get("sub")
        role: Optional[str] = payload.get("role") # Assuming role is in token
        if email is None: # Role might be optional depending on needs
            logger.warning("Token missing email (sub).")
            raise credentials_exception
        # TokenData schema might not be strictly necessary if just passing email/role
        # token_data = TokenData(email=email, role=role)
    except JWTError as e:
        logger.warning(f"JWTError decoding token: {e}")
        raise credentials_exception from e

    user = await db.users.find_one({"email": email})
    if user is None:
        logger.warning(f"User not found for email from token: {email}")
        raise credentials_exception

    # Validate the structure before returning
    # No need to convert _id to id here
    try:
        user_out = UserOut.model_validate(user)
        # Verify role from DB matches token role if necessary
        # if user_out.role != role:
        #     logger.warning(f"Role mismatch for user {email}. Token role: {role}, DB role: {user_out.role}")
        #     raise credentials_exception
        return user_out
    except Exception as e: # Catch validation errors specifically if needed
        logger.error(f"Failed to validate user data from DB for {email}: {e}")
        raise credentials_exception


# --- Get Current User Endpoint ---
@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: UserOut = Depends(get_current_user)):
    """
    Returns the details of the currently authenticated user.
    """
    return current_user