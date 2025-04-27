# LLM_interviewer/server/app/models/user.py

from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime
from bson import ObjectId # Import ObjectId directly

# Import UserRole Literal from the primary schemas file for consistency
try:
    # Assuming UserRole is defined in your updated app/schemas/user.py
    from app.schemas.user import UserRole
except ImportError:
    # Fallback if the import fails (shouldn't happen if schemas/user.py is correct)
    from typing import Literal
    UserRole = Literal["candidate", "hr", "admin"]


class User(BaseModel):
    """
    Represents a User document in the MongoDB database.
    This model includes all fields stored in the collection, including sensitive ones like hashed_password.
    """
    # Use Pydantic v2 model_config
    # Allow arbitrary types like ObjectId
    # Enable populate_by_name to allow mapping from '_id' if data comes in that format
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

    # Use Field with alias for MongoDB's _id, allowing ObjectId type
    id: Optional[ObjectId] = Field(default=None, alias="_id", description="MongoDB document ObjectID")
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    hashed_password: str = Field(...) # Store the hashed password
    role: UserRole # Use the consistent UserRole type
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) # Use timezone-aware UTC default
    updated_at: Optional[datetime] = None # Optional, set on updates
    resume_path: Optional[str] = None
    resume_text: Optional[str] = None
    # Add any other fields stored directly in the user document
    # e.g., is_active: bool = True

    # Example of how you might define helper methods if needed, though often kept in services/repos
    # def check_password(self, plain_password: str) -> bool:
    #     from app.core.security import verify_password # Avoid circular import if possible
    #     return verify_password(plain_password, self.hashed_password)