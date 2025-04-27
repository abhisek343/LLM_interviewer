# LLM_interviewer/server/app/api/routes/admin.py

import logging
from typing import List, Dict, Any # Added Dict, Any
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
from app.core.security import get_current_active_user, verify_admin_user # Import verify_admin_user
# from app.models.user import User # Can often be removed if using UserOut from dependency
from app.schemas.user import UserOut # Import UserOut for response model & dependency type hint
from app.db.mongodb import mongodb # Use the singleton instance
from app.core.config import settings # Use the settings instance directly

# Configure logging
logger = logging.getLogger(__name__)

# --- Helper function to Get ObjectId ---
def get_object_id(id_str: str) -> ObjectId:
    """Converts a string ID to ObjectId, raising HTTPException on failure."""
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError) as e:
        logger.error(f"Invalid ObjectId format: '{id_str}'. Error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ID format: {id_str}")

# --- Router Setup ---
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    # Apply admin verification dependency correctly using the imported function
    dependencies=[Depends(verify_admin_user)]
)

# --- Admin Routes ---

@router.get("/users", response_model=List[UserOut])
async def get_all_users(
    admin_user: UserOut = Depends(verify_admin_user), # Type hint dependency as UserOut
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
) -> List[UserOut]: # Return list of UserOut models (FastAPI handles serialization)
    """
    Retrieves a list of all registered users. (Admin only)
    """
    logger.info(f"Admin user {admin_user.username} requested list of all users.")
    users_collection = db[settings.MONGODB_COLLECTION_USERS]
    users_cursor = users_collection.find()
    users_list = await users_cursor.to_list(length=None) # Fetch all

    response_users_models = []
    for user_doc in users_list:
        try:
            # Validate MongoDB doc into a UserOut Pydantic model instance
            # Pydantic handles the _id -> id aliasing during validation if schema is correct
            user_model_instance = UserOut.model_validate(user_doc)
            response_users_models.append(user_model_instance)
        except Exception as e:
             logger.error(f"Error parsing user document to UserOut: {user_doc}. Error: {e}", exc_info=True)
             # Optionally skip this user or handle error differently

    logger.info(f"Returning {len(response_users_models)} users to admin {admin_user.username}.")
    # Return the list of Pydantic model instances directly
    # FastAPI + response_model should handle serialization and aliasing (_id -> id) correctly now
    return response_users_models

@router.get("/stats")
async def get_system_stats(
    admin_user: UserOut = Depends(verify_admin_user), # Type hint dependency as UserOut
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


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str, # User ID from path parameter (string)
    admin_user: UserOut = Depends(verify_admin_user), # Type hint dependency as UserOut (contains string 'id')
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    """
    Deletes a specified user by their ID. (Admin only)
    Prevents an admin from deleting their own account.
    """
    logger.warning(f"Admin {admin_user.username} attempting to delete user ID: {user_id}")

    # --- Self-deletion check ---
    # admin_user.id comes from UserOut which aliases _id to id (string)
    # user_id comes from the path parameter (string)

    # Optional: Keep debug log if helpful, remove if not needed for production
    # logger.debug(f"Self-delete check: Comparing path user_id='{user_id}' (type: {type(user_id)}) with dependency admin_user.id='{admin_user.id}' (type: {type(admin_user.id)})")

    if user_id == admin_user.id: # Direct string comparison
        logger.error(f"Admin user {admin_user.username} attempted self-deletion (ID: {admin_user.id}). Preventing operation.")
        # --- Ensure HTTPException is raised for production logic ---
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators cannot delete their own account."
        )
        # --- Removed temporary diagnostic logger.critical line ---

    # --- END Self-deletion check ---

    # Validate path param and convert to ObjectId for DB operations *after* self-delete check
    try:
        user_oid_to_delete = ObjectId(user_id)
    except (InvalidId, TypeError):
        logger.error(f"Invalid ObjectId format in path parameter: '{user_id}'")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid user ID format: {user_id}")


    # Find user using ObjectId to ensure they exist before deleting
    user_to_delete = await db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": user_oid_to_delete})
    if not user_to_delete:
        logger.error(f"User with ID {user_id} (ObjectId: {user_oid_to_delete}) not found for deletion.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found."
        )

    # Perform deletion using ObjectId
    try:
        delete_result = await db[settings.MONGODB_COLLECTION_USERS].delete_one({"_id": user_oid_to_delete})

        if delete_result.deleted_count == 1:
            logger.info(f"Successfully deleted user with ID: {user_id} (ObjectId: {user_oid_to_delete}) by admin {admin_user.username}.")
            # Return 204 No Content
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