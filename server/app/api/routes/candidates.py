# LLM_interviewer/server/app/api/routes/candidates.py

import shutil
import uuid
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    status,
    Query
)
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, model_validator
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timezone
import aiofiles
import aiofiles.os

# Core, models, schemas, db
from app.core.security import get_current_active_user
from app.models.user import User, CandidateMappingStatus
from app.db.mongodb import mongodb
from app.core.config import settings
from app.services.resume_parser import parse_resume, ResumeParserError
# Import analyzer service (called during resume upload)
from app.services.resume_analyzer_service import resume_analyzer_service

# Import updated/specific schemas
from app.schemas.user import PyObjectIdStr, CandidateProfileOut, CandidateProfileUpdate
# Import Message schemas
from app.schemas.message import MessageOut, MarkReadRequest, BaseUserInfo # Added BaseUserInfo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/candidate",
    tags=["Candidate"]
)

# --- Configuration Values & Helpers ---
try:
    ALLOWED_EXTENSIONS = set(settings.ALLOWED_RESUME_EXTENSIONS)
except AttributeError: ALLOWED_EXTENSIONS = {"pdf", "docx"}
try:
    UPLOAD_DIRECTORY = Path(settings.UPLOAD_DIR) / settings.RESUME_SUBDIR
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
except Exception as e:
     logger.error(f"Upload directory setup failed: {e}")
     UPLOAD_DIRECTORY = Path("uploads/resumes") # Fallback
     try: UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
     except OSError as mk_e: logger.critical(f"Failed to create fallback upload directory: {mk_e}")

def get_object_id(id_str: str) -> ObjectId:
    try: return ObjectId(str(id_str))
    except Exception: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ID format: {id_str}")

async def require_candidate(current_user: User = Depends(get_current_active_user)):
    if current_user.role != "candidate": raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted.")
    db = mongodb.get_db(); user_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": get_object_id(current_user.id)})
    if not user_doc: raise HTTPException(status_code=404, detail="Candidate user not found.")
    return User.model_validate(user_doc)
# --- End Configuration & Helpers ---


# --- Resume Upload Endpoint ---
@router.post("/resume", response_model=CandidateProfileOut)
async def upload_resume(
    resume: UploadFile = File(...),
    current_candidate_user: User = Depends(require_candidate), # Renamed for clarity
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    """
    Handles resume upload for the candidate.
    Saves file, parses text, runs analysis, updates user record and status.
    """
    logger.info(f"Candidate {current_candidate_user.username} uploading resume.")
    # --- File Validation ---
    file_extension = Path(resume.filename).suffix.lower()
    if not file_extension or file_extension.lstrip('.') not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    user_id_str = str(current_candidate_user.id)
    safe_filename = f"{user_id_str}_{uuid.uuid4()}{file_extension}"
    file_location = UPLOAD_DIRECTORY / safe_filename
    parsed_content: Optional[str] = None
    analysis_result: Dict[str, Any] = {}
    parsing_status = "save pending"; file_saved = False

    # --- Save, Parse, Analyze ---
    try:
        # 1. Save
        async with aiofiles.open(file_location, "wb") as buffer:
            while chunk := await resume.read(8192): await buffer.write(chunk)
        file_saved = True; logger.info(f"Saved candidate resume: {file_location}"); parsing_status = "parse pending"
        # 2. Parse
        try:
            parsed_content = await parse_resume(file_location)
            parsing_status = f"successfully parsed ({len(parsed_content)} chars)" if parsed_content else "parsed empty/unsupported"
            logger.info(f"Candidate Resume Parsing Status: {parsing_status}")
        except ResumeParserError as e: parsing_status = f"parse failed ({e})"; logger.error(f"Parsing failed for {current_candidate_user.username}: {e}", exc_info=False)
        except Exception as e: parsing_status = f"parse failed (unexpected: {type(e).__name__})"; logger.error(f"Unexpected parsing error for {current_candidate_user.username}: {e}", exc_info=True)
        # 3. Analyze
        if parsed_content: # Only analyze if parsing yielded content
            try:
                logger.info(f"Analyzing candidate resume: {current_candidate_user.username}")
                analysis_result = await resume_analyzer_service.analyze_resume(parsed_content)
                logger.info(f"Analysis Results for {current_candidate_user.username}: Skills={len(analysis_result.get('extracted_skills_list',[]))}, YoE={analysis_result.get('estimated_yoe')}")
            except Exception as e: 
                logger.error(f"Error analyzing resume {file_location} for {current_candidate_user.username}: {e}", exc_info=True)
                analysis_result = {} # Ensure it's an empty dict on failure
    except Exception as e: 
        logger.error(f"Failed during save/parse/analyze for {current_candidate_user.username}: {e}", exc_info=True)
        # If file was saved but a subsequent step failed, attempt to delete the saved file
        if file_saved and await aiofiles.os.path.exists(file_location):
            try: await aiofiles.os.remove(file_location); logger.info(f"Cleaned up orphaned file {file_location}")
            except Exception as cleanup_e: logger.error(f"Failed to cleanup orphaned file {file_location}: {cleanup_e}")
        raise HTTPException(status_code=500, detail="Error processing resume file.")
    finally: 
        await resume.close()

    # --- Database Update ---
    update_data = {
        "resume_path": str(file_location.resolve()),
        "resume_text": parsed_content, 
        "extracted_skills_list": analysis_result.get("extracted_skills_list"),
        "estimated_yoe": analysis_result.get("estimated_yoe"),
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Status Update Logic: Only update to 'pending_assignment' if resume was successfully parsed
    # and the current status is 'pending_resume'.
    if file_saved and parsed_content and current_candidate_user.mapping_status == "pending_resume":
        update_data["mapping_status"] = "pending_assignment"
        logger.info(f"Updating candidate {user_id_str} status to 'pending_assignment'.")
    elif file_saved and not parsed_content and current_candidate_user.mapping_status == "pending_resume":
        logger.info(f"Candidate {current_candidate_user.username} uploaded a resume, but parsing failed or yielded no content. Status remains 'pending_resume'.")
        # No change to mapping_status in update_data if parsing fails
    
    final_update_data = {k: v for k, v in update_data.items() if v is not None}
    if "resume_text" not in final_update_data and parsed_content is None: 
        final_update_data["resume_text"] = None
    # Ensure mapping_status is explicitly included if it was determined, even if it's the same as before
    # This handles cases where it might be None and then gets set.
    if "mapping_status" in update_data:
        final_update_data["mapping_status"] = update_data["mapping_status"]
    elif "mapping_status" not in final_update_data and current_candidate_user.mapping_status: # If not set by logic above, retain current
        final_update_data["mapping_status"] = current_candidate_user.mapping_status


    try:
        users_collection = db[settings.MONGODB_COLLECTION_USERS]
        update_result = await users_collection.update_one(
            {"_id": current_candidate_user.id}, 
            {"$set": final_update_data}
        )
        if update_result.matched_count == 0:
            if file_saved and await aiofiles.os.path.exists(file_location):
                 try: await aiofiles.os.remove(file_location)
                 except Exception as e: logger.error(f"Cleanup failed for {file_location} (user not found during update): {e}")
            raise HTTPException(status_code=404, detail="Candidate not found during update.")
        
        logger.info(f"Updated candidate {current_candidate_user.username}. Parse status: {parsing_status}")
        updated_user_doc = await users_collection.find_one({"_id": current_candidate_user.id})
        if not updated_user_doc: 
            raise HTTPException(status_code=500, detail="Failed to retrieve updated candidate profile.")
        return CandidateProfileOut.model_validate(updated_user_doc)
    except Exception as db_e:
        logger.error(f"DB error updating resume info for {current_candidate_user.username}: {db_e}", exc_info=True)
        if file_saved and await aiofiles.os.path.exists(file_location):
             try: await aiofiles.os.remove(file_location)
             except Exception as e: logger.error(f"Cleanup failed for {file_location} (DB error): {e}")
        raise HTTPException(status_code=500, detail="Error updating user record with resume information.")


# --- Profile Endpoints ---
@router.get("/profile", response_model=CandidateProfileOut)
async def get_candidate_profile(current_candidate: User = Depends(require_candidate)):
    logger.info(f"Fetching profile for candidate: {current_candidate.username}")
    return CandidateProfileOut.model_validate(current_candidate)

@router.put("/profile", response_model=CandidateProfileOut)
async def update_candidate_profile(profile_update: CandidateProfileUpdate, current_candidate: User = Depends(require_candidate), db: AsyncIOMotorClient = Depends(mongodb.get_db)):
    logger.info(f"Attempting update profile for candidate: {current_candidate.username}")
    update_data = profile_update.model_dump(exclude_unset=True)
    if not update_data: raise HTTPException(status_code=400, detail="No update data.")
    if "username" in update_data and update_data["username"] != current_candidate.username:
        if await db[settings.MONGODB_COLLECTION_USERS].find_one({"username": update_data["username"]}):
             raise HTTPException(status_code=400, detail="Username already taken.")
    update_data["updated_at"] = datetime.now(timezone.utc)
    try:
        users_collection = db[settings.MONGODB_COLLECTION_USERS]
        res = await users_collection.update_one({"_id": current_candidate.id}, {"$set": update_data})
        if res.matched_count == 0: raise HTTPException(status_code=404, detail="Candidate not found.")
        updated_user_doc = await users_collection.find_one({"_id": current_candidate.id})
        return CandidateProfileOut.model_validate(updated_user_doc)
    except Exception as e: logger.error(f"Error updating profile: {e}", exc_info=True); raise HTTPException(status_code=500)


# --- Messaging Endpoints ---

@router.get("/messages", response_model=List[MessageOut])
async def get_candidate_messages(
    current_candidate: User = Depends(require_candidate),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
    limit: int = Query(20, ge=1, le=100), 
    skip: int = Query(0, ge=0)
):
    logger.info(f"Candidate {current_candidate.username} fetching messages (limit={limit}, skip={skip}).")
    messages_collection = db["messages"] 
    candidate_oid = current_candidate.id
    pipeline = [
        {"$match": {"recipient_id": candidate_oid}},
        {"$sort": {"sent_at": -1}},
        {"$skip": skip},
        {"$limit": limit},
        {"$lookup": {
            "from": settings.MONGODB_COLLECTION_USERS, "localField": "sender_id",
            "foreignField": "_id", "as": "sender_info_doc"
        }},
        {"$unwind": {"path": "$sender_info_doc", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "_id": 1, "sender_id": 1, "recipient_id": 1, "subject": 1, "content": 1,
            "sent_at": 1, "read_status": 1, "read_at": 1,
            "sender_info": { 
                "$cond": {
                   "if": {"$ifNull": ["$sender_info_doc", False]},
                   "then": {"id": "$sender_info_doc._id", "username": "$sender_info_doc.username"},
                   "else": None 
                }
            }
        }}
    ]
    try:
        message_cursor = messages_collection.aggregate(pipeline)
        messages_data = await message_cursor.to_list(length=limit)
        response_list = [MessageOut.model_validate(msg) for msg in messages_data]
        return response_list
    except Exception as e:
        logger.error(f"Error fetching messages for candidate {candidate_oid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not retrieve messages.")


@router.post("/messages/mark-read", status_code=status.HTTP_200_OK, response_model=Dict[str, int])
async def mark_messages_as_read(
    read_request: MarkReadRequest,
    current_candidate: User = Depends(require_candidate),
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    logger.info(f"Candidate {current_candidate.username} marking messages as read: {read_request.message_ids}")
    messages_collection = db["messages"]
    candidate_oid = current_candidate.id
    now = datetime.now(timezone.utc)
    message_oids_to_mark = []
    for msg_id_str in read_request.message_ids:
        try: message_oids_to_mark.append(get_object_id(msg_id_str))
        except HTTPException: raise HTTPException(status_code=400, detail=f"Invalid message ID format: {msg_id_str}") 
    if not message_oids_to_mark: return {"modified_count": 0}
    try:
        update_result = await messages_collection.update_many(
            {"_id": {"$in": message_oids_to_mark}, "recipient_id": candidate_oid, "read_status": False},
            {"$set": {"read_status": True, "read_at": now}}
        )
        modified_count = update_result.modified_count
        logger.info(f"Marked {modified_count} messages as read for candidate {candidate_oid}.")
        return {"modified_count": modified_count}
    except Exception as e:
        logger.error(f"Error marking messages as read for candidate {candidate_oid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update message status.")
