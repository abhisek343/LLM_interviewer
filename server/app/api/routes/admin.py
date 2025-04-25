# LLM_interviewer/server/app/api/routes/admin.py

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Body, Query
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timezone

# Core, models, schemas, db
from app.core.security import verify_admin_user
from app.models.user import User, CandidateMappingStatus, HrStatus
from app.schemas.user import UserOut, HrProfileOut, CandidateProfileOut, PyObjectIdStr
# from pydantic import BaseModel, Field # BaseModel and Field will be imported via AssignHrRequest or other schemas
from app.schemas.application_request import HRMappingRequestOut
from app.schemas.search import RankedHR  # Import schema for search results
from app.schemas.admin import AssignHrRequest # Import AssignHrRequest

from app.db.mongodb import mongodb
from app.core.config import settings
from app.services.invitation_service import InvitationService, InvitationError
from app.services.search_service import SearchService  # Import SearchService

# Configure logging
logger = logging.getLogger(__name__)


# --- Helper & Schema --- (No change)
def get_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(str(id_str))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid ID format: {id_str}")


# AssignHrRequest is now imported from app.schemas.admin


# --- Router Setup --- (No change)
router = APIRouter(
    prefix="/admin", tags=["Admin"], dependencies=[Depends(verify_admin_user)]
)


# --- Admin User/Stats Routes --- (No change)
@router.get("/users", response_model=List[UserOut])
async def get_all_users(
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
) -> List[UserOut]:
    logger.info(f"Admin {admin_user.username} requested list of all users.")
    users_collection = db[settings.MONGODB_COLLECTION_USERS]
    users_list = await users_collection.find().to_list(length=None)
    return [UserOut.model_validate(u) for u in users_list]


@router.get("/stats")
async def get_system_stats(
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    logger.info(f"Admin {admin_user.username} requested system stats.")
    # ... (fetch counts) ...
    users_collection = db[settings.MONGODB_COLLECTION_USERS]
    interviews_collection = db[settings.MONGODB_COLLECTION_INTERVIEWS]
    total_users = await users_collection.count_documents({})
    total_interviews_scheduled = await interviews_collection.count_documents({})
    total_interviews_completed = await interviews_collection.count_documents(
        {"status": "completed"}
    )
    total_hr_mapped = await users_collection.count_documents(
        {"role": "hr", "hr_status": "mapped"}
    )
    total_candidates_assigned = await users_collection.count_documents(
        {"role": "candidate", "mapping_status": "assigned"}
    )
    stats = {
        "total_users": total_users,
        "total_hr_mapped": total_hr_mapped,
        "total_candidates_assigned": total_candidates_assigned,
        "total_interviews_scheduled": total_interviews_scheduled,
        "total_interviews_completed": total_interviews_completed,
        "llm_service_status": "Operational (Placeholder)",
    }
    return stats


@router.delete("/users/{user_id_to_delete}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id_to_delete: str,
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    """
    Deletes a specified user by ID. Prevents self-delete or deleting other Admins.
    If deleting an HR user, un-assigns their candidates.
    """
    logger.warning(
        f"Admin {admin_user.username} attempting to delete user ID: {user_id_to_delete}"
    )
    target_user_oid = get_object_id(user_id_to_delete)

    if target_user_oid == admin_user.id:
        raise HTTPException(
            status_code=403, detail="Administrators cannot delete their own account."
        )

    # Fetch target user *once*
    target_user = await db[settings.MONGODB_COLLECTION_USERS].find_one(
        {"_id": target_user_oid}
    )
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id_to_delete} not found.",
        )

    target_role = target_user.get("role")
    if target_role == "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrators cannot delete other administrator accounts.",
        )

    # --- Perform deletion and related actions ---
    try:
        # ** Un-assign Candidates if deleting an HR user **
        if target_role == "hr":
            logger.info(
                f"Deleting HR user {target_user_oid}. Un-assigning their candidates."
            )
            unassign_result = await db[settings.MONGODB_COLLECTION_USERS].update_many(
                # Find candidates assigned to this specific HR
                {"role": "candidate", "assigned_hr_id": target_user_oid},
                # Reset their assignment and status
                {
                    "$set": {
                        "assigned_hr_id": None,
                        "mapping_status": "pending_assignment",  # Back to pending assignment state
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            logger.info(
                f"Unassigned {unassign_result.modified_count} candidates previously assigned to HR {target_user_oid}."
            )
            # Optional: Delete pending applications/requests involving this HR?
            # await db["hr_mapping_requests"].delete_many({"$or": [{"requester_id": target_user_oid}, {"target_id": target_user_oid}]})

        # ** Delete the target user **
        delete_result = await db[settings.MONGODB_COLLECTION_USERS].delete_one(
            {"_id": target_user_oid}
        )

        if delete_result.deleted_count == 1:
            logger.info(
                f"Successfully deleted user {user_id_to_delete} (Role: {target_role}) by admin {admin_user.username}."
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        else:
            # This case implies the user existed moments ago but couldn't be deleted (rare)
            logger.error(
                f"Delete operation failed for user {user_id_to_delete} despite finding user."
            )
            raise HTTPException(
                status_code=500, detail="User found but could not be deleted."
            )

    except Exception as e:
        logger.error(
            f"Error during user deletion or candidate un-assignment (ID: {user_id_to_delete}): {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="An error occurred during the deletion process."
        )


# --- HR Application/Mapping Management Endpoints --- (Integration mostly done)


@router.get("/hr-applications", response_model=List[HRMappingRequestOut])
async def get_hr_applications(
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    # ... (Implementation uses InvitationService) ...
    logger.info(f"Admin {admin_user.username} fetching pending HR applications.")
    invitation_service = InvitationService(db=db)
    try:
        pending_apps_data = await invitation_service.get_pending_applications_for_admin(
            admin_user.id
        )
        return [HRMappingRequestOut.model_validate(app) for app in pending_apps_data]
    except Exception as e:
        logger.error(f"Error fetching HR applications: {e}", exc_info=True)
        raise HTTPException(status_code=500)


@router.post("/hr-applications/{application_id}/accept", response_model=Dict[str, str])
async def accept_hr_application(
    application_id: str,
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    # ... (Implementation uses InvitationService) ...
    logger.info(
        f"Admin {admin_user.username} accepting application ID {application_id}"
    )
    app_oid = get_object_id(application_id)
    invitation_service = InvitationService(db=db)
    try:
        if await invitation_service.accept_request_or_application(app_oid, admin_user):
            return {"message": f"Application {application_id} accepted."}
        else:
            raise HTTPException(status_code=500, detail="Acceptance failed.")
    except InvitationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error accepting application {application_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500)


@router.post("/hr-applications/{application_id}/reject", response_model=Dict[str, str])
async def reject_hr_application(
    application_id: str,
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    # ... (Implementation uses InvitationService) ...
    logger.info(
        f"Admin {admin_user.username} rejecting application ID {application_id}"
    )
    app_oid = get_object_id(application_id)
    invitation_service = InvitationService(db=db)
    try:
        if await invitation_service.reject_request_or_application(app_oid, admin_user):
            return {"message": f"Application {application_id} rejected."}
        else:
            raise HTTPException(status_code=500, detail="Rejection failed.")
    except InvitationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error rejecting application {application_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500)


# --- HR Search/Request Endpoints --- (Integration mostly done)


@router.get("/search-hr", response_model=List[RankedHR])
async def search_hr_profiles(
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
    status_filter: Optional[HrStatus] = Query(None),
    keyword: Optional[str] = Query(None),
    yoe_min: Optional[int] = Query(None, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    # ... (Implementation uses SearchService placeholder) ...
    logger.info(
        f"Admin {admin_user.username} searching HR profiles. Status: {status_filter}, Keyword: {keyword}, YoE Min: {yoe_min}"
    )
    search_service = SearchService(db=db)
    try:
        return await search_service.search_hr_profiles(
            keyword=keyword, yoe_min=yoe_min, status_filter=status_filter, limit=limit
        )
    except Exception as e:
        logger.error(f"Error searching HR profiles: {e}", exc_info=True)
        raise HTTPException(status_code=500)


@router.post("/hr-mapping-requests/{hr_user_id}", response_model=HRMappingRequestOut)
async def send_hr_mapping_request(
    hr_user_id: str,
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    # ... (Implementation uses InvitationService) ...
    logger.info(
        f"Admin {admin_user.username} sending mapping request to HR {hr_user_id}"
    )
    hr_user_oid = get_object_id(hr_user_id)
    invitation_service = InvitationService(db=db)
    try:
        return HRMappingRequestOut.model_validate(
            await invitation_service.create_admin_request(admin_user, hr_user_oid)
        )
    except InvitationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending mapping request: {e}", exc_info=True)
        raise HTTPException(status_code=500)


# --- Candidate Assignment Endpoint --- (No changes needed)


@router.post(
    "/candidates/{candidate_id}/assign-hr",
    response_model=CandidateProfileOut,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/AssignHrRequest"}
                }
            }
        }
    },
)
async def assign_hr_to_candidate(
    candidate_id: str,
    assign_request: AssignHrRequest,
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db),
):
    # ... (Implementation remains the same as previous version) ...
    candidate_oid = get_object_id(candidate_id)
    hr_oid_to_assign = get_object_id(assign_request.hr_id)
    logger.info(
        f"Admin {admin_user.username} assigning HR {hr_oid_to_assign} to Candidate {candidate_oid}"
    )
    # Validation ...
    candidate_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one(
        {"_id": candidate_oid, "role": "candidate"}
    )
    assert candidate_doc and candidate_doc.get("mapping_status") == "pending_assignment"
    hr_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one(
        {"_id": hr_oid_to_assign, "role": "hr"}
    )
    assert hr_doc and hr_doc.get("hr_status") == "mapped"
    # Assignment ...
    update_data = {
        "$set": {
            "mapping_status": "assigned",
            "assigned_hr_id": hr_oid_to_assign,
            "updated_at": datetime.now(timezone.utc),
        }
    }
    update_result = await db[settings.MONGODB_COLLECTION_USERS].update_one(
        {"_id": candidate_oid}, update_data
    )
    if update_result.modified_count == 1:
        updated_candidate_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one(
            {"_id": candidate_oid}
        )
        return CandidateProfileOut.model_validate(updated_candidate_doc)
    else:
        logger.error(f"Failed assign HR for candidate {candidate_id}.")
        raise HTTPException(status_code=500)
