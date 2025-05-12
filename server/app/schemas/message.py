# LLM_interviewer/server/app/schemas/message.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# Import ObjectId handling and potentially basic user info from user schemas
from .user import PyObjectIdStr


# --- Embedded User Info Schema ---
# Minimal info for the sender display
# Consider moving to a common schemas file (e.g., schemas/common.py) if used elsewhere
class BaseUserInfo(BaseModel):
    # Using only ID and username for brevity in message lists
    id: PyObjectIdStr
    username: str
    # email: Optional[str] = None # Optional, maybe not needed here
    # role: Optional[UserRole] = None # Optional

    model_config = ConfigDict(from_attributes=True)


# --- Message Schemas ---


class MessageBase(BaseModel):
    """Base schema containing common message fields, often used for creation."""

    recipient_id: PyObjectIdStr = Field(..., description="ID of the message recipient")
    subject: Optional[str] = Field(
        None, max_length=200, description="Subject of the message"
    )
    content: str = Field(..., description="The content/body of the message")


class MessageCreate(MessageBase):
    """
    Schema used as the request body when sending a new message (e.g., HR to Candidate).
    The sender_id is determined from the authenticated user's token in the route.
    """

    # Inherits recipient_id, subject, content
    pass

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipient_id": "6819421abecde9ce24f85d5b",  # Example Candidate ID
                "subject": "Invitation to Proceed",
                "content": "We have reviewed your resume and would like to invite you to the next stage...",
            }
        }
    )

# Schema for creating message content when recipient_id is from path param
class MessageContentCreate(BaseModel):
    subject: Optional[str] = Field(None, max_length=200, description="Subject of the message")
    content: str = Field(..., description="The content/body of the message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Invitation to Proceed",
                "content": "We have reviewed your resume and would like to invite you to the next stage...",
            }
        }
    )

class MessageOut(MessageBase):
    """
    Schema for representing a message in API responses (e.g., listing messages in an inbox).
    Includes full details and metadata like sender info and read status.
    """

    id: PyObjectIdStr = Field(..., alias="_id")  # The message's own ID
    sender_id: PyObjectIdStr  # ID of the sender

    sent_at: datetime
    read_status: bool
    read_at: Optional[datetime] = None

    # Embed basic sender details populated by the route/service
    sender_info: Optional[BaseUserInfo] = Field(
        None, description="Basic info of the sender"
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None},
    )


class MarkReadRequest(BaseModel):
    """Schema for marking one or more messages as read."""

    message_ids: List[PyObjectIdStr] = Field(
        ..., min_length=1, description="List of message IDs to mark as read"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message_ids": ["681cae4f5634b1e5b7c8d01a", "681cae4f5634b1e5b7c8d01b"]
            }
        }
    )
