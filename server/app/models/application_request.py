# LLM_interviewer/server/app/models/application_request.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime, timezone # Added timezone
from bson import ObjectId

# Assuming PyObjectIdStr and UserRole are needed for type hints if not directly used
# For simplicity, if PyObjectIdStr is complex, ObjectId can be used for model fields
# and then converted to string in schemas. UserRole is for requester_role/target_role.
from app.schemas.user import PyObjectIdStr, UserRole # Schemas can be imported by models if they are simple type definitions

# --- Literal types for the model ---
# These should ideally be defined in one place if shared across models and schemas,
# or defined here if specific to this model's interaction with the DB.
# For now, defining them here to match what invitation_service expects to import.
RequestMappingType = Literal["application", "request"]
RequestMappingStatus = Literal["pending", "accepted", "rejected", "cancelled"]


class HRMappingRequest(BaseModel):
    """
    Pydantic model representing an HR Mapping Request/Application document in MongoDB.
    """
    id: PyObjectIdStr = Field(..., alias="_id", description="The document's MongoDB ObjectId")
    
    request_type: RequestMappingType = Field(..., description="Type of interaction: 'application' (HR to Admin) or 'request' (Admin to HR)")
    
    requester_id: PyObjectIdStr = Field(..., description="ID of the user who initiated the request/application")
    requester_role: UserRole = Field(..., description="Role of the requester (HR or Admin)")
    
    target_id: PyObjectIdStr = Field(..., description="ID of the user who is the target of the request/application")
    target_role: UserRole = Field(..., description="Role of the target (Admin or HR)")
    
    status: RequestMappingStatus = Field(..., description="Current status of the request/application")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional fields that might be added for context, though not strictly in every doc
    # message: Optional[str] = Field(None, description="Optional message associated with the request")

    model_config = ConfigDict(
        populate_by_name=True,  # Allows using '_id' from DB and mapping to 'id'
        arbitrary_types_allowed=True, # Allows ObjectId if used directly before PyObjectIdStr validation
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat()} # For any direct JSON export
    )
