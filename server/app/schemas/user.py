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
    # Removed __get_validators__ for Pydantic v2, relying on __get_pydantic_core_schema__
    # @classmethod
    # def __get_validators__(cls):
    #     yield cls.validate

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
        arbitrary_types_allowed=True, # Allow types like ObjectId if used internally before validation
        from_attributes=True  # Allow creating from model instances
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
    id: PyObjectIdStr = Field(..., alias="_id", serialization_alias="id") # Use alias for MongoDB _id field
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

# --- Status Enums/Literals ---

HrStatus = Literal[
    "pending_profile",
    "profile_complete",
    "application_pending", # Applied to an admin
    "admin_request_pending", # Admin sent a request to this HR
    "mapped",
    "suspended"
]

CandidateMappingStatus = Literal[
    "pending_resume",       # Candidate registered, needs to upload resume
    "pending_assignment",   # Candidate has resume, waiting for HR assignment by Admin
    "assigned",             # Candidate assigned to an HR
    "interview_scheduled",  # Interview has been scheduled for the candidate
    "interview_completed"   # Candidate has completed an interview
]

# --- Candidate Specific Schemas ---

class CandidateProfileOut(UserOut): # Inherits from UserOut
    # Add candidate-specific fields that should be visible
    resume_text: Optional[str] = None
    # Alias field names if they differ in the database model vs. desired API output
    extracted_skills_list: Optional[List[str]] = Field(None, alias="extracted_skills_list")
    estimated_yoe: Optional[float] = Field(None, alias="estimated_yoe")
    mapping_status: Optional[str] = None # e.g., "pending_assignment", "pending_resume", "assigned"
    assigned_hr_id: Optional[PyObjectIdStr] = None # Added assigned_hr_id

    # Add other fields that might be part of a candidate's viewable profile
    # phone_number: Optional[str] = None
    # profile_summary: Optional[str] = None
    # completed_interviews_count: Optional[int] = Field(default=0)
    # pending_interviews_count: Optional[int] = Field(default=0)

    model_config = ConfigDict(
        populate_by_name=True, # Ensures aliases are used for population
        arbitrary_types_allowed=True # If using complex types not directly supported by Pydantic
    )

class CandidateProfileUpdate(BaseModel):
    # Fields a candidate can update in their profile
    # These should match the fields that the update endpoint in candidates.py actually processes
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    # If other direct profile fields are updatable by the candidate:
    # phone_number: Optional[str] = None
    # profile_summary: Optional[str] = None
    # years_of_experience: Optional[int] = Field(None, ge=0) # Example if candidate self-reports

    # Password update is often a separate, more secure endpoint or part of general UserUpdate
    # password: Optional[str] = Field(None, min_length=8)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra='ignore' # Ignore extra fields if any are sent in the request
    )

# --- HR Specific Schemas ---

class HrProfileOut(UserOut): # Inherits from UserOut
    # Add HR-specific fields that should be visible
    # These are examples; actual fields depend on the User model for HR roles
    hr_status: Optional[HrStatus] = None 
    years_of_experience: Optional[int] = Field(None, ge=0)
    company: Optional[str] = None
    admin_manager_id: Optional[PyObjectIdStr] = None # Added admin_manager_id
    # specialization: Optional[List[str]] = None # Example
    # mapped_admin_id: Optional[PyObjectIdStr] = None # If HR is mapped to an Admin

    # Fields related to HR's management capabilities, if any displayed on their profile
    # managed_candidates_count: Optional[int] = Field(default=0)
    # open_positions_count: Optional[int] = Field(default=0)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

class HrProfileUpdate(BaseModel):
    # Fields an HR user can update in their profile
    username: Optional[str] = Field(None, min_length=3, max_length=50) # Inherited, but can be here for clarity
    email: Optional[EmailStr] = None # Inherited

    # HR-specific updatable fields
    years_of_experience: Optional[int] = Field(None, ge=0, description="Years of professional experience.")
    company: Optional[str] = Field(None, max_length=100, description="Current or most recent company.")
    # specialization: Optional[List[str]] = Field(None, description="Areas of HR specialization.")
    # phone_number: Optional[str] = Field(None, max_length=20) # Example

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra='ignore' # Ignore extra fields if any are sent in the request
    )

# --- Admin Specific Schemas ---

class AdminBasicInfo(BaseModel):
    id: PyObjectIdStr = Field(..., alias="_id", serialization_alias="id") # Explicit serialization_alias
    username: str
    email: EmailStr

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True  # Added from_attributes
    )
