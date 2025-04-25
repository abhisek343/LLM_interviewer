# LLM_interviewer/server/app/api/routes/admin.py

import logging
from typing import List
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Response # Import Response for 204 status
)
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from bson.errors import InvalidId

# Core, models, schemas, db
from app.core.security import get_current_active_user
from app.models.user import User, UserRole
from app.schemas.user import UserResponse # Import the response schema
from app.db.mongodb import mongodb # Use the singleton instance
from app.core.config import settings # Use the settings instance directly

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Helper function to Get ObjectId ---
# (Duplicating here for self-containment, consider moving to a shared util)
def get_object_id(id_str: str) -> ObjectId:
    """Converts a string ID to ObjectId, raising HTTPException on failure."""
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError) as e:
        logger.error(f"Invalid ObjectId format: '{id_str}'. Error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ID format: {id_str}")

# --- Helper Dependency for Admin Verification ---
async def verify_admin_user(current_user: User = Depends(get_current_active_user)):
    """Dependency to check if the current user is an admin."""
    if current_user.role != UserRole.admin:
        logger.warning(f"Forbidden attempt to access admin route by user {current_user.username} (role: {current_user.role})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted. Administrator privileges required."
        )
    return current_user

# --- Router Setup ---
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    # Apply admin verification to all routes in this router
    dependencies=[Depends(verify_admin_user)]
)

# --- Admin Routes ---

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    admin_user: User = Depends(verify_admin_user), # Explicit dependency for clarity
    db: AsyncIOMotorClient = Depends(mongodb.get_db) # Use dependency injection
):
    """
    Retrieves a list of all registered users. (Admin only)
    """
    logger.info(f"Admin user {admin_user.username} requested list of all users.")
    users_collection = db[settings.MONGODB_COLLECTION_USERS]
    users_cursor = users_collection.find()
    users_list = await users_cursor.to_list(length=None) # Fetch all

    response_users = []
    for user_doc in users_list:
        # Ensure _id is converted to string for 'id' field if UserResponse expects 'id'
        user_doc["id"] = str(user_doc["_id"])
        try:
            response_users.append(UserResponse(**user_doc))
        except Exception as e:
             logger.error(f"Error parsing user document to UserResponse: {user_doc}. Error: {e}", exc_info=True)
             # Optionally skip this user or handle error differently

    logger.info(f"Returning {len(response_users)} users to admin {admin_user.username}.")
    return response_users

@router.get("/stats")
async def get_system_stats(
    admin_user: User = Depends(verify_admin_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    """
    Retrieves basic system statistics. (Admin only - Placeholder)
    """
    logger.info(f"Admin user {admin_user.username} requested system stats.")
    try:
        users_collection = db[settings.MONGODB_COLLECTION_USERS]
        interviews_collection = db[settings.MONGODB_COLLECTION_INTERVIEWS]
        # responses_collection = db[settings.MONGODB_COLLECTION_RESPONSES] # If needed

        total_users = await users_collection.count_documents({})
        total_interviews_scheduled = await interviews_collection.count_documents({})
        total_interviews_completed = await interviews_collection.count_documents({"status": "completed"})
        # total_responses = await responses_collection.count_documents({}) # Example

        stats = {
            "total_users": total_users,
            "total_interviews_scheduled": total_interviews_scheduled,
            "total_interviews_completed": total_interviews_completed,
            "llm_service_status": "Operational (Placeholder)" # Check gemini_service status if possible
        }
        logger.info(f"Returning system stats to admin {admin_user.username}: {stats}")
        return stats
    except Exception as e:
         logger.error(f"Error fetching system stats: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail="Could not retrieve system statistics.")

# --- NEW Endpoint: Delete User ---
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str, # User ID from path parameter
    admin_user: User = Depends(verify_admin_user), # Ensures requester is admin
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    """
    Deletes a specified user by their ID. (Admin only)
    Prevents an admin from deleting their own account.
    """
    logger.warning(f"Admin {admin_user.username} attempting to delete user ID: {user_id}")
    user_oid_to_delete = get_object_id(user_id) # Validate and convert ID

    # Prevent admin self-deletion
    if str(user_oid_to_delete) == str(admin_user.id):
        logger.error(f"Admin user {admin_user.username} attempted self-deletion.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators cannot delete their own account."
        )

    # Find user to ensure they exist before deleting
    user_to_delete = await db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": user_oid_to_delete})
    if not user_to_delete:
        logger.error(f"User with ID {user_id} not found for deletion.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )

    # Perform deletion
    try:
        delete_result = await db[settings.MONGODB_COLLECTION_USERS].delete_one({"_id": user_oid_to_delete})

        if delete_result.deleted_count == 1:
            logger.info(f"Successfully deleted user with ID: {user_id} by admin {admin_user.username}.")
            # --- Consideration: Data Cascade ---
            # Should we delete related data? e.g., interviews scheduled BY this user (if HR/Admin)?
            # Interviews SCHEDULED FOR this user (if candidate)? Candidate responses?
            # This requires careful planning based on application logic.
            # For now, we only delete the user document.
            # Example (Potential Cleanup - USE WITH CAUTION):
            # if user_to_delete.get("role") == "candidate":
            #     await db[settings.MONGODB_COLLECTION_INTERVIEWS].delete_many({"candidate_id": user_oid_to_delete})
            #     await db[settings.MONGODB_COLLECTION_RESPONSES].delete_many({"candidate_id": user_oid_to_delete})
            # --- End Consideration ---
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        else:
            # This case should be rare if find_one succeeded, but handle defensively
            logger.error(f"User {user_id} found but delete operation failed (deleted count: {delete_result.deleted_count}).")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User found but could not be deleted."
            )
    except Exception as e:
        logger.error(f"Error during user deletion (ID: {user_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting the user."
        )

# Add other admin endpoints as needed (e.g., update user role when backend is ready)