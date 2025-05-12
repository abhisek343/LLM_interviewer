# LLM_interviewer/server/app/models/message.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime, timezone
from bson import ObjectId

# --- Define Literal types (Optional) ---
# Example: If you anticipate different types of system messages later
# MessageType = Literal[
#     "candidate_invitation",
#     "notification",
#     "general"
# ]
# --- End Literal types ---


class Message(BaseModel):
    """
    Represents a message document stored in the 'messages' collection (example name).
    Used primarily for HR sending invitation messages to Candidates.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        validate_assignment=True
    )

    id: Optional[ObjectId] = Field(default=None, alias="_id", description="MongoDB document ObjectID")

    sender_id: ObjectId = Field(..., description="ObjectId of the user who sent the message (e.g., HR user)")
    recipient_id: ObjectId = Field(..., description="ObjectId of the user who should receive the message (e.g., Candidate user)")

    # Optional: Add sender/recipient role for easier querying?
    # sender_role: Literal["hr", "admin", "system"] = Field(...)
    # recipient_role: Literal["candidate", "hr", "admin"] = Field(...)

    # Optional: Subject line
    subject: Optional[str] = Field(None, max_length=200, description="Subject of the message")

    content: str = Field(..., description="The main content/body of the message")

    # Optional: Message Type
    # message_type: MessageType = Field(default="general", description="Type of message")

    # Timestamps & Status
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    read_status: bool = Field(default=False, description="Indicates if the recipient has marked the message as read")
    read_at: Optional[datetime] = Field(default=None, description="Timestamp when the message was marked as read")


    class Meta:
        # collection_name = "messages"
        pass

    # --- Potential Indexes ---
    # Consider adding indexes in MongoDB for efficient querying:
    # - On `recipient_id` and `sent_at` (for fetching user's inbox, sorted)
    # - On `recipient_id` and `read_status` (for fetching unread messages)