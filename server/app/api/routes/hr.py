# LLM_interviewer/server/app/api/routes/hr.py

import logging
from typing import List, Dict, Any, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Response,
    UploadFile,
    File,
    Body,
    Query,
)
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone
from pydantic import BaseModel, Field # Added Pydantic imports
import asyncio
import uuid
from pathlib import Path
import aiofiles
import aiofiles.os

# Core, models, schemas, db
from app.core.security import get_current_active_user
from app.models.user import User, HrStatus
from app.models.application_request import HRMappingRequest
from app.schemas.user import UserOut, HrProfileOut, HrProfileUpdate, PyObjectIdStr, AdminBasicInfo # Added AdminBasicInfo import
from app.schemas.application_request import HRMappingRequestOut
from app.schemas.search import RankedCandidate
from app.schemas.message import MessageOut, MessageContentCreate 

from app.db.mongodb import mongodb
from app.core.config import settings

# Import Services
from app.services.invitation_service import InvitationService, InvitationError
from app.services.search_service import SearchService
# RankedCandidate is now imported from app.schemas.search (already listed above)

# Import resume parser AND analyzer
from app.services.resume_parser import parse_resume, ResumeParserError
from app.services.resume_analyzer_service import (
    resume_analyzer_service,
)  # Import analyzer

# Configure logging
logger = logging.getLogger(__name__)

# --- Upload Directory Config ---
try:
    HR_UPLOAD_DIRECTORY = Path(settings.UPLOAD_DIR) / getattr(
        settings, "HR_RESUME_SUBDIR", "hr_resumes"
    )
    HR_ALLOWED_EXTENSIONS = set(settings.ALLOWED_RESUME_EXTENSIONS)
    HR_UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    logger.info(f"HR Resume upload directory: {HR_UPLOAD_DIRECTORY}")
except AttributeError as e:
    logger.error(f"Settings for HR uploads missing: {e}. Using defaults.")
    HR_UPLOAD_DIRECTORY = Path("uploads/hr_resumes")
    HR_ALLOWED_EXTENSIONS = {"pdf", "docx"}
    try:
        HR_UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    except OSError as mk_e:
        logger.critical(f"Failed to create HR upload directory: {mk_e}")
except OSError as e:
    logger.critical(
        f"CRITICAL: Failed to create HR upload directory {HR_UPLOAD_DIRECTORY}: {e}"
    )
# --- End Upload Config ---


# --- Helper function & Dependency ---
def get_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(str(id_str))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid ID format: {id_str}")


async def require_hr(current_user_dep: User = Depends(get_current_active_user)):
    # ... (implementation remains same) ...
    if current_user_dep.role != "hr":
        raise HTTPException(status_code=403, detail="Operation requires HR privileges.")
    db = mongodb.get_db()
    hr_user_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one(
        {"_id": get_object_id(current_user_dep.id)}
    )
    if not hr_user_doc:
        raise HTTPException(status_code=404, detail="HR user not found.")

    # Convert string OIDs to ObjectId before Pydantic validation
    if "admin_manager_id" in hr_user_doc and isinstance(hr_user_doc["admin_manager_id"], str):
        try:
            hr_user_doc["admin_manager_id"] = ObjectId(hr_user_doc["admin_manager_id"])
        except Exception:
            logger.error(f"Invalid ObjectId string for admin_manager_id in require_hr: {hr_user_doc['admin_manager_id']}")
            # Let Pydantic validation fail it if it's truly invalid.
            pass 
    
    # Though assigned_hr_id is typically for Candidate, good practice if User model might be shared/reused
    if "assigned_hr_id" in hr_user_doc and isinstance(hr_user_doc["assigned_hr_id"], str):
        try:
            hr_user_doc["assigned_hr_id"] = ObjectId(hr_user_doc["assigned_hr_id"])
        except Exception:
            pass

    return User.model_validate(hr_user_doc)


# --- Router Setup ---
router = APIRouter(prefix="/hr", tags=["HR"], dependencies=[Depends(require_hr)])

# --- HR Profile Management ---


@router.post("/profile-details", response_model=HrProfileOut)
async def update_hr_profile_details(
    profile_data: HrProfileUpdate,
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    # ... (implementation remains same) ...
    logger.info(f"HR {current_hr_user.username} updating profile details.")
    update_doc = profile_data.model_dump(exclude_unset=True)
    update_doc["updated_at"] = datetime.now(timezone.utc)
    has_resume = bool(current_hr_user.resume_path)
    has_yoe = (
        update_doc.get("years_of_experience") is not None
        or current_hr_user.years_of_experience is not None
    )
    if has_resume and has_yoe and current_hr_user.hr_status == "pending_profile":
        update_doc["hr_status"] = "profile_complete"
        logger.info("HR profile complete.")
    result = await db[settings.MONGODB_COLLECTION_USERS].update_one(
        {"_id": current_hr_user.id}, {"$set": update_doc}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="HR User not found.")
    updated_user = await db[settings.MONGODB_COLLECTION_USERS].find_one(
        {"_id": current_hr_user.id}
    )
    return HrProfileOut.model_validate(updated_user)


@router.post("/resume", response_model=HrProfileOut)
async def upload_hr_resume(
    resume: UploadFile = File(...),
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    """
    Allows an HR user to upload/update their resume.
    Saves file, parses text, runs analysis (skills, YoE), updates user record,
    and updates status if profile becomes complete.
    """
    logger.info(f"HR user {current_hr_user.username} uploading/updating resume.")

    # --- File Validation ---
    file_extension = Path(resume.filename).suffix.lower()
    if not file_extension or file_extension.lstrip(".") not in HR_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(HR_ALLOWED_EXTENSIONS)}",
        )

    user_id_str = str(current_hr_user.id)
    safe_filename = f"{user_id_str}_{uuid.uuid4()}{file_extension}"
    file_location = HR_UPLOAD_DIRECTORY / safe_filename
    parsed_content: Optional[str] = None
    analysis_result: Dict[str, Any] = {}  # To store results from analyzer service
    parsing_status = "save pending"
    file_saved = False

    # --- Save, Parse, and Analyze ---
    try:
        # 1. Save File
        async with aiofiles.open(file_location, "wb") as buffer:
            while chunk := await resume.read(8192):
                await buffer.write(chunk)
        file_saved = True
        logger.info(f"Saved HR resume: {file_location}")
        parsing_status = "parse pending"

        # 2. Parse Text
        try:
            parsed_content = await parse_resume(file_location)
            parsing_status = (
                f"successfully parsed ({len(parsed_content)} chars)"
                if parsed_content
                else "parsed empty/unsupported"
            )
            logger.info(f"HR Resume Parsing Status: {parsing_status}")
        except ResumeParserError as parse_e:
            parsing_status = f"parse failed ({parse_e})"
            logger.error(f"Parsing HR resume failed: {parse_e}", exc_info=False)
        except Exception as parse_e:
            parsing_status = f"parse failed (unexpected: {type(parse_e).__name__})"
            logger.error(f"Unexpected HR parsing error: {parse_e}", exc_info=True)

        # 3. Analyze Text (if parsed successfully)
        if parsed_content:
            try:
                logger.info(
                    f"Analyzing parsed HR resume text for {current_hr_user.username}..."
                )
                # Call the analyzer service
                analysis_result = await resume_analyzer_service.analyze_resume(
                    parsed_content
                )
                logger.info(
                    f"HR Resume Analysis Results: Skills={len(analysis_result.get('extracted_skills_list',[]))}, YoE={analysis_result.get('estimated_yoe')}"
                )
            except Exception as analyze_e:
                logger.error(
                    f"Error analyzing HR resume {file_location}: {analyze_e}",
                    exc_info=True,
                )
                # Decide if failure to analyze should prevent profile completion? For now, just log it.
                analysis_result = {}  # Ensure it's an empty dict on failure

    except Exception as save_e:
        logger.error(
            f"Failed to save HR resume {file_location}: {save_e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Error saving resume file.")
    finally:
        await resume.close()
    # --- End Save, Parse, Analyze ---

    # --- Database Update ---
    update_doc = {
        "resume_path": str(file_location.resolve()),
        "resume_text": parsed_content,  # Store parsed text
        # Store analysis results - ** ADJUST FIELD NAMES AS NEEDED **
        "extracted_skills_list": analysis_result.get("extracted_skills_list"),
        "estimated_yoe": analysis_result.get("estimated_yoe"),
        "updated_at": datetime.now(timezone.utc),
    }
    # Remove analysis fields if they are None to avoid storing nulls explicitly unless desired
    if update_doc["extracted_skills_list"] is None:
        del update_doc["extracted_skills_list"]
    if update_doc["estimated_yoe"] is None:
        del update_doc["estimated_yoe"]

    # Check if profile is now complete (Resume uploaded AND YoE exists on record)
    # Use current_hr_user.years_of_experience which reflects DB state *before* this update for YoE check
    has_yoe_on_record = current_hr_user.years_of_experience is not None
    is_profile_complete = file_saved and has_yoe_on_record

    if is_profile_complete and current_hr_user.hr_status == "pending_profile":
        update_doc["hr_status"] = "profile_complete"
        logger.info(
            f"HR user {current_hr_user.username} profile marked as complete post-resume."
        )

    try:
        result = await db[settings.MONGODB_COLLECTION_USERS].update_one(
            {"_id": current_hr_user.id}, {"$set": update_doc}
        )
        if result.matched_count == 0:
            if file_saved and await aiofiles.os.path.exists(file_location):
                try:
                    await aiofiles.os.remove(file_location)
                except Exception as e:
                    logger.error(f"Cleanup failed for {file_location}: {e}")
            raise HTTPException(
                status_code=404, detail="HR User not found during update."
            )

        logger.info(
            f"Updated HR {current_hr_user.username} resume/analysis info. Parse status: {parsing_status}"
        )
        updated_user = await db[settings.MONGODB_COLLECTION_USERS].find_one(
            {"_id": current_hr_user.id}
        )
        return HrProfileOut.model_validate(updated_user)
    except Exception as db_e:
        logger.error(f"DB error updating HR resume info: {db_e}", exc_info=True)
        if file_saved and await aiofiles.os.path.exists(file_location):
            try:
                await aiofiles.os.remove(file_location)
            except Exception as e:
                logger.error(f"Cleanup failed for {file_location}: {e}")
        raise HTTPException(
            status_code=500, detail="Error updating user record with resume info."
        )


# --- Admin Application/Mapping Workflow --- (No changes needed here)
# ... (endpoints /admins, /apply/{admin_id}, /pending-admin-requests, etc. remain the same) ...
@router.get("/admins", response_model=List[AdminBasicInfo])
async def list_admins_for_application(
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    if current_hr_user.hr_status != "profile_complete":
        raise HTTPException(
            status_code=403,
            detail=f"Complete profile first (Status: {current_hr_user.hr_status}).",
        )
    admins = (
        await db[settings.MONGODB_COLLECTION_USERS]
        .find({"role": "admin"}, projection={"_id": 1, "username": 1, "email": 1})
        .to_list(length=None)
    )
    return [AdminBasicInfo.model_validate(admin) for admin in admins]


@router.post(
    "/apply/{admin_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=HRMappingRequestOut,
)
async def apply_to_admin(
    admin_id: str,
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    target_admin_oid = get_object_id(admin_id)
    logger.info(f"HR {current_hr_user.username} applying to Admin {admin_id}")
    invitation_service = InvitationService(db=db)
    try:
        return HRMappingRequestOut.model_validate(
            await invitation_service.create_hr_application(
                current_hr_user, target_admin_oid
            )
        )
    except InvitationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying to Admin {admin_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500)


@router.get("/pending-admin-requests", response_model=List[HRMappingRequestOut])
async def get_pending_admin_requests(
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    logger.info(f"HR {current_hr_user.username} fetching pending admin requests.")
    invitation_service = InvitationService(db=db)
    try:
        pending_requests_data = await invitation_service.get_pending_requests_for_hr(
            current_hr_user.id
        )
        return [
            HRMappingRequestOut.model_validate(req) for req in pending_requests_data
        ]
    except Exception as e:
        logger.error(f"Error fetching pending requests: {e}", exc_info=True)
        raise HTTPException(status_code=500)


@router.post("/accept-admin-request/{request_id}", response_model=HrProfileOut)
async def accept_admin_request(
    request_id: str,
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    request_oid = get_object_id(request_id)
    logger.info(f"HR {current_hr_user.username} accepting request {request_id}")
    invitation_service = InvitationService(db=db)
    try:
        if await invitation_service.accept_request_or_application(
            request_oid, current_hr_user
        ):
            updated_hr_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one(
                {"_id": current_hr_user.id}
            )
            return HrProfileOut.model_validate(updated_hr_doc)
        else:
            raise HTTPException(status_code=500, detail="Acceptance failed.")
    except InvitationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error accepting request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500)


@router.post("/reject-admin-request/{request_id}", response_model=Dict[str, str])
async def reject_admin_request(
    request_id: str,
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    request_oid = get_object_id(request_id)
    logger.info(f"HR {current_hr_user.username} rejecting request {request_id}")
    invitation_service = InvitationService(db=db)
    try:
        if await invitation_service.reject_request_or_application(
            request_oid, current_hr_user
        ):
            return {"message": f"Request {request_id} rejected."}
        else:
            raise HTTPException(status_code=500, detail="Rejection failed.")
    except InvitationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error rejecting request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500)


@router.post("/unmap", response_model=HrProfileOut)
async def unmap_from_admin(
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    logger.info(
        f"HR {current_hr_user.username} unmapping from Admin {current_hr_user.admin_manager_id}"
    )
    invitation_service = InvitationService(db=db)
    try:
        if await invitation_service.hr_unmap(current_hr_user):
            updated_hr_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one(
                {"_id": current_hr_user.id}
            )
            return HrProfileOut.model_validate(updated_hr_doc)
        else:
            raise HTTPException(status_code=400, detail="Unmap failed.")
    except InvitationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during unmap: {e}", exc_info=True)
        raise HTTPException(status_code=500)


# --- Candidate Interaction Endpoints ---


@router.get("/search-candidates", response_model=List[RankedCandidate])
async def search_candidates(
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
    keyword: Optional[str] = Query(None),
    required_skills: Optional[List[str]] = Query(None),
    yoe_min: Optional[int] = Query(None, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    # ... (Implementation uses SearchService) ...
    if current_hr_user.hr_status != "mapped":
        raise HTTPException(
            status_code=403, detail="Action requires HR user to be mapped."
        )
    logger.info(f"Mapped HR {current_hr_user.username} searching candidates...")
    search_service = SearchService(db=db)
    try:
        return await search_service.search_candidates(
            keyword=keyword,
            required_skills=required_skills,
            yoe_min=yoe_min,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Error searching candidates: {e}", exc_info=True)
        raise HTTPException(status_code=500)


@router.post("/candidate-invitations/{candidate_id}", response_model=Dict[str, str])
async def send_candidate_invitation_message(
    candidate_id: str,
    message_create: MessageContentCreate,  # Changed to MessageContentCreate
    current_hr_user: User = Depends(require_hr),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    """Allows a mapped HR user to send an 'invitation message' to a candidate."""
    # --- Logic Implemented ---
    if current_hr_user.hr_status != "mapped":
        raise HTTPException(
            status_code=403, detail="Action requires HR user to be mapped to an Admin."
        )

    target_candidate_oid = get_object_id(candidate_id)
    logger.info(
        f"Mapped HR {current_hr_user.username} sending invitation message to Candidate {candidate_id}."
    )

    # Validate Candidate exists and is pending assignment
    candidate_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one(
        {"_id": target_candidate_oid, "role": "candidate"}
    )
    if not candidate_doc:
        raise HTTPException(status_code=404, detail="Target candidate not found.")
    if candidate_doc.get("mapping_status") != "pending_assignment":
        raise HTTPException(
            status_code=400,
            detail=f"Candidate cannot be invited at this stage (Status: {candidate_doc.get('mapping_status')}).",
        )

    # Create Message Document
    messages_collection = db["messages"]  # Use actual collection name
    message_doc = {
        "sender_id": current_hr_user.id,
        "recipient_id": target_candidate_oid,
        "subject": message_create.subject
        or f"Invitation from {current_hr_user.username}",
        "content": message_create.content,
        "sent_at": datetime.now(timezone.utc),
        "read_status": False,
        "read_at": None,
    }
    try:
        result = await messages_collection.insert_one(message_doc)
        if not result.inserted_id:
            raise Exception("Message insertion failed.")
        logger.info(
            f"Message {result.inserted_id} sent to candidate {candidate_id} by HR {current_hr_user.username}."
        )
        # TODO: Consider changing candidate status to 'invited' here?
        return {"message": f"Invitation message sent to Candidate {candidate_id}."}
    except Exception as e:
        logger.error(
            f"Failed to save message to candidate {candidate_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to send message.")
