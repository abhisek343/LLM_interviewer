# LLM_interviewer/server/app/models/user.py

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, EmailStr

UserRole = Literal["admin", "hr", "candidate"]

class User(BaseModel):
    # Added id field, often useful when retrieving from DB and converting _id
    # Use Field alias to map from MongoDB's _id
    id: Optional[str] = Field(alias="_id", default=None)
    username: str
    email: EmailStr
    hashed_password: str # Note: Consider excluding this from default API responses
    role: UserRole
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Resume related fields
    resume_path: Optional[str] = None # Path to the stored resume file

    # --- Added resume_text field ---
    resume_text: Optional[str] = None # Parsed text content of the resume
    # --- End added field ---

    class Config:
        populate_by_name = True # Allows using alias ('_id') during model creation
        json_schema_extra = {
            "example": {
                "id": "60d5ecf1b3f8f5a9f3e8e1c1",
                "username": "johndoe",
                "email": "john@example.com",
                "role": "candidate",
                "created_at": "2024-01-01T00:00:00Z",
                "resume_path": "/path/to/uploads/resumes/user_id_uuid.pdf",
                "resume_text": "John Doe\nSoftware Engineer\nSkills: Python, FastAPI...\nExperience: ..." # Example text
            }
        }
        # If you are directly fetching BSON ObjectId, you might need this:
        # arbitrary_types_allowed = True
        # json_encoders = {ObjectId: str} # Handle ObjectId serialization if needed directly in model