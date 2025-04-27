# LLM_interviewer/server/app/schemas/user.py

from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict # Import v2 components
from typing import List, Optional, Literal, Any
from datetime import datetime
from bson import ObjectId

# Define allowed user roles using Literal for better type safety
UserRole = Literal["candidate", "hr", "admin"]

# --- Custom ObjectId Handling ---
# Reusable type for handling ObjectId validation and serialization
# Pydantic v2 has better built-in support for types like this.
class PyObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any, _info) -> str: # Changed handler signature for v2
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            # Optionally convert back to ObjectId internally if needed, but return str
            # return ObjectId(v) # No, return str for API consistency
            return v
        raise ValueError(f"Not a valid ObjectId string: {v}")

    # Pydantic v2 uses __get_pydantic_core_schema__ for deeper integration
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
        from pydantic_core import core_schema
        return core_schema.with_info_plain_validator_function(
            cls.validate, # Use the same validation logic
             serialization=core_schema.to_string_ser_schema(), # Ensure serialization to string
        )

# --- Base Schemas ---
class BaseUser(BaseModel):
    # Use v2 model_config instead of Config class
    model_config = ConfigDict(
        populate_by_name=True, # Keep aliasing enabled
        arbitrary_types_allowed=True # Allow types like ObjectId if used internally before validation
    )

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    role: UserRole # Use the Literal type for role

    # V2 Field Validator for 'role'
    @field_validator('role', mode='before')
    @classmethod
    def check_role(cls, value: str) -> str:
        allowed_roles = list(UserRole.__args__) # Get allowed roles from Literal
        if value not in allowed_roles:
            raise ValueError(f"Invalid role '{value}'. Must be one of: {', '.join(allowed_roles)}")
        return value

# Schema for user creation (includes password)
class UserCreate(BaseUser):
    password: str = Field(..., min_length=8)

# Schema for user update (optional fields)
class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    # Role update might require specific logic/permissions, handle in route if needed
    # role: Optional[UserRole] = None
    password: Optional[str] = Field(None, min_length=8) # Optional password update

# Schema for user output (excludes password, includes ID)
class UserOut(BaseUser):
    id: PyObjectIdStr = Field(..., alias="_id") # Use alias for MongoDB _id field
    created_at: Optional[datetime] = None
    resume_path: Optional[str] = None # Keep these optional output fields

# Schema for representing user data in responses (can wrap UserOut)
class UserResponse(BaseModel):
    message: str
    user: Optional[UserOut] = None
    users: Optional[List[UserOut]] = None # For returning lists of users

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    # Store email (subject) and potentially role from token payload
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None