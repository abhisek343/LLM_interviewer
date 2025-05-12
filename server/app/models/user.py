# LLM_interviewer/server/app/models/user.py

from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, Literal # Added Literal
from datetime import datetime, timezone # Ensure timezone is imported
from bson import ObjectId # Import ObjectId directly

# --- Define Literal types for statuses ---
# Candidate Mapping Statuses
CandidateMappingStatus = Literal[
    "pending_resume", # Initial state after registration
    "pending_assignment", # Resume uploaded, waiting for Admin assignment
    "assigned" # Assigned to an HR by Admin
]

# HR Statuses
HrStatus = Literal[
    "pending_profile", # Initial state after registration
    "profile_complete", # Resume/YoE uploaded, ready to apply/be requested
    "application_pending", # Applied to an Admin, waiting for acceptance
    "admin_request_pending", # An Admin has sent a mapping request, waiting for HR acceptance
    "mapped" # Accepted by/has accepted an Admin, ready for work
]
# --- End Literal types ---


# Import UserRole Literal from the primary schemas file for consistency
try:
    # Assuming UserRole is defined in your updated app/schemas/user.py
    from app.schemas.user import UserRole
except ImportError:
    # Fallback if the import fails (shouldn't happen if schemas/user.py is correct)
    UserRole = Literal["candidate", "hr", "admin"]


class User(BaseModel):
    """
    Represents a User document in the MongoDB database.
    This model includes all fields stored in the collection, including sensitive ones like hashed_password,
    and new fields for status tracking and relationships based on the refined workflow.
    """
    # Use Pydantic v2 model_config
    # Allow arbitrary types like ObjectId
    # Enable populate_by_name to allow mapping from '_id' if data comes in that format
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        validate_assignment=True # Useful for ensuring assigned values match types
    )

    # Use Field with alias for MongoDB's _id, allowing ObjectId type
    id: Optional[ObjectId] = Field(default=None, alias="_id", description="MongoDB document ObjectID")
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    hashed_password: str = Field(...) # Store the hashed password
    role: UserRole # Use the consistent UserRole type

    # --- Role-Specific Fields & Statuses ---

    # For Candidates
    mapping_status: Optional[CandidateMappingStatus] = Field(
        default=None, # Set dynamically upon registration based on role
        description="Candidate's status in the HR mapping workflow"
    )
    assigned_hr_id: Optional[ObjectId] = Field(
        default=None,
        description="ObjectId of the HR user assigned to this Candidate by an Admin"
    )

    # For HR
    hr_status: Optional[HrStatus] = Field(
        default=None, # Set dynamically upon registration based on role
        description="HR user's status in the Admin mapping/application workflow"
    )
    admin_manager_id: Optional[ObjectId] = Field(
        default=None,
        description="ObjectId of the Admin this HR user is currently mapped to"
    )
    years_of_experience: Optional[int] = Field(
        default=None,
        ge=0, # Ensure non-negative
        description="Years of experience (primarily for HR profile)"
    )
    # Add other HR-specific profile fields as needed, e.g.:
    # hr_specialization: Optional[str] = None

    # --- Common Fields ---
    resume_path: Optional[str] = Field(
        default=None,
        description="Path to the uploaded resume file (applies to Candidate and HR)"
    )
    resume_text: Optional[str] = Field(
        default=None,
        description="Parsed text content of the resume (applies to Candidate and HR)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Can be updated automatically

    # --- Added field validator/setter logic examples (Optional but recommended) ---
    # Pydantic v2 allows using @model_validator or specific field validators
    # Example: Automatically set initial status based on role upon creation
    # This might be better handled in the registration service/route logic,
    # but demonstrates how models can enforce rules.

    # @model_validator(mode='before')
    # def set_initial_status(cls, values):
    #     # This runs before standard validation, be careful
    #     role = values.get('role')
    #     if role == 'candidate' and 'mapping_status' not in values:
    #         values['mapping_status'] = 'pending_resume'
    #     elif role == 'hr' and 'hr_status' not in values:
    #         values['hr_status'] = 'pending_profile'
    #     return values

    # Example: Automatically update `updated_at` timestamp on modification
    # Pydantic v2 doesn't have a built-in hook exactly like V1's pre_update.
    # Updates to `updated_at` are usually handled in the database update logic (e.g., setting `$currentDate` or in the service layer).

# Note: Remember to adjust your registration logic (`api/routes/auth.py`)
# to set the appropriate initial status ('mapping_status' or 'hr_status')
# based on the user's role when creating a new user document.