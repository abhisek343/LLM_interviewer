# LLM_interviewer/server/app/schemas/application_request.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime

# Import ObjectId handling and Role literal from user schemas
from .user import PyObjectIdStr, UserRole

# --- Literal types ---
# Defines the types of mapping interactions
RequestMappingType = Literal["application", "request"]
# Defines the possible statuses for these interactions
RequestMappingStatus = Literal["pending", "accepted", "rejected", "cancelled"]
# --- End Literal types ---


# --- Embedded User Info Schema ---
# Used to display basic info about requester/target in lists
class UserInfoBasic(BaseModel):
    id: PyObjectIdStr
    username: str
    email: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


# --- Main Application/Request Schemas ---


class HRMappingRequestBase(BaseModel):
    """Base schema for HR Mapping Request/Application data."""

    request_type: RequestMappingType
    requester_id: PyObjectIdStr  # ID of the initiating user
    target_id: PyObjectIdStr  # ID of the user who needs to respond
    status: RequestMappingStatus


class HRMappingRequestOut(HRMappingRequestBase):
    """
    Schema for representing an HR Mapping Request/Application in API responses.
    Includes timestamps and embedded basic info about related users.
    """

    id: PyObjectIdStr = Field(..., alias="_id")  # The request document's own ID
    created_at: datetime
    updated_at: datetime

    # Embed basic user details populated by the service/route
    requester_info: Optional[UserInfoBasic] = Field(
        None, description="Basic info of the user who initiated (HR or Admin)"
    )
    target_info: Optional[UserInfoBasic] = Field(
        None, description="Basic info of the user who should respond (Admin or HR)"
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,  # Allow reading '_id' as 'id'
        arbitrary_types_allowed=True,
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None},
    )
