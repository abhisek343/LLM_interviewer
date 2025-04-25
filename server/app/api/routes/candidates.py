# LLM_interviewer/server/app/api/routes/candidate.py

import shutil
import uuid
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    status
)
from motor.motor_asyncio import AsyncIOMotorClient
# --- Updated Pydantic import ---
from pydantic import BaseModel, Field, EmailStr, validator, model_validator # Added model_validator
# --- End Updated Pydantic import ---
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime # Import datetime
import aiofiles

# Core and DB imports
# Assuming get_current_active_user is correctly defined in security.py now
from app.core.security import get_current_active_user
from app.models.user import User, UserRole # Import User model
from app.db.mongodb import mongodb # Use singleton instance
from app.core.config import settings # Import the settings instance
from app.services.resume_parser import parse_resume, ResumeParserError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/candidate",
    tags=["Candidate"]
)

# --- Configuration Values from Settings ---
try:
    ALLOWED_EXTENSIONS = set(settings.ALLOWED_RESUME_EXTENSIONS)
    logger.info(f"Allowed resume extensions from settings: {ALLOWED_EXTENSIONS}")
except AttributeError:
    logger.error("Setting 'ALLOWED_RESUME_EXTENSIONS' not found in config.py! Using default.")
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}

try:
    UPLOAD_DIRECTORY = Path(settings.RESUME_UPLOAD_DIR)
    logger.info(f"Resume upload directory from settings: {UPLOAD_DIRECTORY}")
except AttributeError:
     logger.error("Setting 'RESUME_UPLOAD_DIR' not found in config.py! Using default.")
     UPLOAD_DIRECTORY = Path("uploads/resumes")

try:
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directory ensured: {UPLOAD_DIRECTORY.resolve()}")
except OSError as e:
    logger.critical(f"CRITICAL: Failed to create upload directory {UPLOAD_DIRECTORY}: {e}")
# --- End Configuration ---


# --- Helper function to Get ObjectId ---
def get_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError) as e:
        logger.error(f"Invalid ObjectId format: '{id_str}'. Error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ID format: {id_str}")

# --- Helper Dependency for Candidate Verification ---
async def require_candidate(current_user: User = Depends(get_current_active_user)):
    if current_user.role != UserRole.candidate:
        logger.warning(f"Forbidden access attempt by user {current_user.username} (role: {current_user.role}) to Candidate route.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. Candidate role required."
        )
    return current_user
# --- End Helper ---


# --- Pydantic Models for Profile ---
class CandidateProfileOut(BaseModel):
    id: str = Field(alias="_id")
    username: str
    email: EmailStr
    role: UserRole
    resume_path: Optional[str] = None
    created_at: datetime

    class Config:
        populate_by_name = True
        # Corrected example schema
        json_schema_extra = {
            "example": {
                "_id": "60d5ecf1b3f8f5a9f3e8e1c1",
                "username": "candidate_example",
                "email": "candidate@example.com",
                "role": "candidate",
                "resume_path": "/path/to/uploads/resumes/user_id_uuid.pdf",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class CandidateProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    # tech_stack: Optional[List[str]] = None # Add if needed

    # --- MODIFIED: Pydantic V2 Model Validator ---
    @model_validator(mode='after')
    def check_at_least_one_value(self) -> 'CandidateProfileUpdate':
        # Check if any fields were actually provided in the input data
        if not self.model_dump(exclude_unset=True):
            raise ValueError('At least one field must be provided for update')
        return self
    # --- END MODIFIED VALIDATOR ---

    # Using ConfigDict for V2 compatibility (optional but recommended)
    model_config = {
         "json_schema_extra": { "example": { "username": "new_name" } }
    }
    # --- End Pydantic Models ---


@router.post("/resume", status_code=status.HTTP_200_OK)
async def upload_resume(
    resume: UploadFile = File(..., description=f"Candidate resume. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"),
    current_user: User = Depends(require_candidate),
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    """
    Handles resume upload for the currently authenticated candidate user.
    Saves file, parses text, updates user record.
    """
    file_extension = Path(resume.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        logger.error(f"Invalid file type '{file_extension}' from {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    user_id_str = str(current_user.id)
    safe_filename = f"{user_id_str}_{uuid.uuid4()}{file_extension}"
    file_location = UPLOAD_DIRECTORY / safe_filename
    parsed_content: Optional[str] = None
    parsing_status = "save pending"

    logger.info(f"Saving resume for {current_user.username} to {file_location}")
    try:
        # Use aiofiles for async file operations
        async with aiofiles.open(file_location, "wb") as buffer:
            # Read file in chunks to avoid memory issues
            while chunk := await resume.read(8192):
                await buffer.write(chunk)

        logger.info(f"Successfully saved resume file: {file_location}")
        parsing_status = "parse pending"

        # Attempt to parse
        try:
            parsed_content = await parse_resume(file_location)
            if parsed_content:
                parsed_len = len(parsed_content) if isinstance(parsed_content, str) else 0
                parsing_status = f"successfully parsed ({parsed_len} chars)"
                logger.info(f"Parsed resume for {current_user.username}.")
            else:
                parsing_status = "parsed empty/unsupported"
                logger.warning(f"Parsing yielded no content for {file_location}.")
        except Exception as parse_e:
            parsing_status = f"parse failed ({type(parse_e).__name__})"
            logger.error(f"Parsing failed for {file_location}: {parse_e}", exc_info=True)

    except Exception as save_e:
        logger.error(f"Failed to save resume {file_location}: {save_e}", exc_info=True)
        try:
            file_location.unlink(missing_ok=True)
        except Exception as unlink_e:
            logger.error(f"Error during cleanup of failed upload {file_location}: {unlink_e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error saving resume file.")
    finally:
        await resume.close()

    # Update user record
    update_data = {"resume_path": str(file_location.resolve())}
    if parsed_content is not None:
        update_data["resume_text"] = parsed_content

    try:
        users_collection = db[settings.MONGODB_COLLECTION_USERS]
        user_oid = get_object_id(user_id_str)
        update_result = await users_collection.update_one(
            {"_id": user_oid},
            {"$set": update_data}
        )

        if update_result.matched_count == 0:
            logger.error(f"User {user_id_str} not found during resume path update.")
            try:
                file_location.unlink(missing_ok=True)
            except Exception as unlink_e:
                logger.error(f"Error during cleanup of orphaned upload {file_location}: {unlink_e}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User record not found.")

        if update_result.modified_count == 0:
            logger.warning(f"User {user_id_str} resume info update didn't modify doc (perhaps path was the same?).")

        logger.info(f"Updated user {current_user.username} with resume info (parsing status: {parsing_status})")

    except HTTPException:
        raise
    except Exception as db_e:
        logger.error(f"DB error updating resume info for {current_user.username}: {db_e}", exc_info=True)
        try:
            file_location.unlink(missing_ok=True)
            logger.info(f"Cleaned up {file_location} after DB error.")
        except Exception as unlink_e:
            logger.error(f"Error during cleanup of upload {file_location} after DB error: {unlink_e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating user record.")

    return {
        "message": "Resume uploaded successfully",
        "file_path": str(file_location.resolve()),
        "parsing_status": parsing_status
    }


@router.get("/profile", response_model=CandidateProfileOut)
async def get_candidate_profile(
    current_user: User = Depends(require_candidate)
):
    """ Retrieves profile information for the currently authenticated candidate. """
    logger.info(f"Fetching profile for candidate: {current_user.username} (ID: {current_user.id})")
    try:
        # Convert the User model (which might be slightly different internally)
        # to the CandidateProfileOut response model.
        # model_validate handles alias mapping (_id -> id)
        return CandidateProfileOut.model_validate(current_user)
    except Exception as e:
        logger.error(f"Error preparing profile response for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving profile data.")


@router.put("/profile", response_model=CandidateProfileOut)
async def update_candidate_profile(
    profile_update: CandidateProfileUpdate, # Data to update from request body
    current_user: User = Depends(require_candidate),
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    """ Updates profile information for the currently authenticated candidate. """
    logger.info(f"Attempting to update profile for candidate: {current_user.username} (ID: {current_user.id})")

    # Get update data, excluding fields not present in the request
    update_data = profile_update.model_dump(exclude_unset=True)

    # The model_validator in CandidateProfileUpdate already checks if update_data is empty

    # Optional: Add validation for username uniqueness if changed
    if "username" in update_data and update_data["username"] != current_user.username:
        existing_user = await db[settings.MONGODB_COLLECTION_USERS].find_one(
            {"username": update_data["username"]}
        )
        if existing_user:
            logger.warning(f"Username '{update_data['username']}' already taken.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken.")

    logger.info(f"Update data for user {current_user.username}: {update_data}")
    try:
        users_collection = db[settings.MONGODB_COLLECTION_USERS]
        user_oid = get_object_id(str(current_user.id))
        update_result = await users_collection.update_one( {"_id": user_oid}, {"$set": update_data} )

        if update_result.matched_count == 0:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found during update.")
        if update_result.modified_count == 0:
             logger.info(f"Profile for user {current_user.username} not modified (no changes submitted or data was identical).")
             # Return current profile if nothing changed
             updated_user_doc = await users_collection.find_one({"_id": user_oid})
        else:
             logger.info(f"Successfully updated profile for user {current_user.username}.")
             updated_user_doc = await users_collection.find_one({"_id": user_oid})

        if not updated_user_doc:
            # This should ideally not happen if matched_count was > 0
            logger.error(f"Failed to retrieve updated profile for user {current_user.username} after update operation.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve updated profile.")

        # Use model_validate to create the Pydantic model from the dict
        return CandidateProfileOut.model_validate(updated_user_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while updating the profile.")