# LLM_interviewer/server/app/schemas/user.py

from pydantic import BaseModel, EmailStr, Field, ConfigDict, BeforeValidator # Import ConfigDict and BeforeValidator
from typing import Optional, Annotated # Import Annotated
from datetime import datetime
from app.models.user import UserRole # Import UserRole from the models
from bson import ObjectId # Import ObjectId

# --- Helper function for ObjectId to string conversion ---
# This function will run before Pydantic tries to validate the 'id' field as a string.
def object_id_to_str(v):
    if isinstance(v, ObjectId):
        return str(v)
    # If it's already a string (e.g., from request body), pass it through
    if isinstance(v, str):
        return v
    # Raise error for other unexpected types
    raise ValueError(f"Expected ObjectId or str, received {type(v)}")

# --- Custom type using Annotated and BeforeValidator ---
# This tells Pydantic to run object_id_to_str on the input before validating it as a string.
PyObjectIdStr = Annotated[str, BeforeValidator(object_id_to_str)]

# --- Base User Schema ---
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

# --- Schema for User Creation ---
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User password")
    role: UserRole = Field(..., description="User role (admin, hr, or candidate)")

    model_config = ConfigDict( # Use model_config in Pydantic v2
        json_schema_extra = {
            "example": {
                "username": "newcandidate",
                "email": "candidate@example.com",
                "password": "strongpassword123",
                "role": "candidate"
            }
        }
    )

# --- Schema for User Output (General API Responses) ---
class UserOut(UserBase):
    # Use the custom type PyObjectIdStr for the id field
    id: PyObjectIdStr = Field(alias="_id", description="User's unique ID")
    role: UserRole
    created_at: datetime
    resume_path: Optional[str] = None

    model_config = ConfigDict( # Use model_config in Pydantic v2
        from_attributes = True, # Keep ORM mode enabled if needed elsewhere
        populate_by_name = True # Allow populating by field name OR alias ('_id')
        # arbitrary_types_allowed=True # Not strictly needed if using BeforeValidator explicitly
    )
    # Removed json_schema_extra from UserOut as the example ID might confuse if not str

# --- Schema specifically for Admin User List Response ---
# Inherits from UserOut, so it gets the corrected id handling
class UserResponse(UserOut):
    pass

# --- Schema for Token Response (Login/Register) ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# --- Schema for Data inside JWT Token ---
class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None
    # id: Optional[str] = None # ID is usually looked up via email (sub)