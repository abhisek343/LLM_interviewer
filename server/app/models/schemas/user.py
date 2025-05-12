# LLM_interviewer/server/app/schemas/user.py

from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from typing import List, Optional, Literal, Any
from datetime import datetime
from bson import ObjectId

# Import status literals defined in the model file
# It's often good practice to define these literals in schemas too,
# especially if they are used in request/response validation directly.
# Re-defining them here ensures schemas are self-contained regarding allowed values.
UserRole = Literal["candidate", "hr", "admin"]
CandidateMappingStatus = Literal["pending_resume", "pending_assignment", "assigned"]
HrStatus = Literal["pending_profile", "profile_complete", "application_pending", "admin_request_pending", "mapped"]
# --- End Status Literals ---


# --- Custom ObjectId Handling ---
# (No changes needed here)
class PyObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any, _info) -> str: # Changed handler signature for v2
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError(f"Not a valid ObjectId string: {v}")

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
        from pydantic_core import core_schema
        return core_schema.with_info_plain_validator_function(
            cls.validate,
             serialization=core_schema.to_string_ser_schema(),
        )

# --- Base Schemas ---
class BaseUser(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    role: UserRole

    @field_validator('role', mode='before')
    @classmethod
    def check_role(cls, value: str) -> str:
        allowed_roles = list(UserRole.__args__)
        if value not in allowed_roles:
            raise ValueError(f"Invalid role '{value}'. Must be one of: {', '.join(allowed_roles)}")
        return value

# --- User Creation & Update ---

# Schema for user creation (includes password)
class UserCreate(BaseUser):
    password: str = Field(..., min_length=8)
    # Note: Initial status (mapping_status/hr_status) will be set in the route logic,
    # based on the 'role' provided here. It's not part of the creation payload itself.

# General schema for user update (optional fields) - May need refinement later
class UserUpdate(BaseModel):
    # Used potentially by admin or user self-update (limit fields appropriately in routes)
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8) # Optional password update

# --- HR Specific Schemas ---

# Schema for HR updating their profile details (YoE, etc.)
class HrProfileUpdate(BaseModel):
    years_of_experience: Optional[int] = Field(None, ge=0, description="Years of relevant experience")
    # Add other updatable HR fields here, e.g.:
    # specialization: Optional[str] = None

    model_config = ConfigDict(
         json_schema_extra={
             "example": {
                 "years_of_experience": 5,
                 # "specialization": "Tech Recruiting"
            }
        }
    )

# --- Output Schemas ---

# Basic Schema for user output (excludes password, includes ID)
# Keeping this relatively clean - status/relationship fields can be added
# to more specific schemas used in Admin/HR contexts if needed.
class UserOut(BaseUser):
    id: PyObjectIdStr = Field(..., alias="_id")
    created_at: Optional[datetime] = None
    # Including resume_path here as it was present before, applicable to both roles potentially
    resume_path: Optional[str] = None

    model_config = ConfigDict(
        from_attributes = True, # Enable ORM mode equivalent for V2
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None}
    )


# Specific output schema for HR Profile view (includes HR-specific fields)
class HrProfileOut(UserOut): # Inherits fields from UserOut
    hr_status: Optional[HrStatus] = None
    admin_manager_id: Optional[PyObjectIdStr] = None # Expose the mapped Admin ID as string
    years_of_experience: Optional[int] = None
    # Add other HR fields to expose, e.g.:
    # specialization: Optional[str] = None
    resume_text: Optional[str] = Field(None, description="Parsed resume text for HR profile") # Added for clarity


# Specific output schema for Candidate view (e.g., in Admin/HR context)
class CandidateProfileOut(UserOut): # Inherits fields from UserOut
    mapping_status: Optional[CandidateMappingStatus] = None
    assigned_hr_id: Optional[PyObjectIdStr] = None # Expose assigned HR ID as string
    resume_text: Optional[str] = Field(None, description="Parsed resume text for Candidate profile") # Added for clarity


# Schema for representing user data in responses (can wrap UserOut or other Out schemas)
# No changes needed here for now
class UserResponse(BaseModel):
    message: str
    user: Optional[UserOut] = None # Could be Union[UserOut, HrProfileOut, CandidateProfileOut] depending on context
    users: Optional[List[UserOut]] = None # For returning lists of users


# --- Token Schemas ---
# No changes needed here
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None