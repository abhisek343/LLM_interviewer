# LLM_interviewer/server/app/schemas/admin.py
from pydantic import BaseModel, Field # Removed ConfigDict as it's not used here now
from app.schemas.user import PyObjectIdStr
from app.core.schema_utils import clean_model_title # Keep import for now

@clean_model_title
class AssignHrRequest(BaseModel):
    hr_id: PyObjectIdStr = Field(..., description="The MongoDB ObjectId of the HR user to assign.")

    # The title will be set by the @clean_model_title decorator.
    # We can still keep json_schema_extra if needed.
    class Config:
        title = "AssignHrRequest" # Explicitly set title
        json_schema_extra = {
            "example": {
                "hr_id": "60d5ec49f72f3b5e9f1d0a1b"
            }
        }
        # populate_by_name = True # If these were needed, ensure decorator or manual add
        # arbitrary_types_allowed = True

# Add other Admin-specific request/response schemas here as needed
