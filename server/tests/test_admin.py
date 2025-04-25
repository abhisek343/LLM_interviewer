# LLM_interviewer/server/tests/test_admin.py

import pytest
from fastapi import status
from app.db.mongodb import mongodb # Keep for type hinting if needed
from app.core.config import settings
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient # Import for type hint
import logging # Import logging

# Fixtures like client, test_users_and_tokens, admin_token, hr_token, candidate_token,
# candidate_user, admin_user, test_db are provided by conftest.py

logger = logging.getLogger(__name__) # Add logger

# --- Tests for GET /admin/users ---

@pytest.mark.asyncio
async def test_get_users_by_admin(client, admin_token, test_users_and_tokens, test_db): # Added test_db (though not directly used, ensures override)
    """Test admin successfully fetching the user list."""
    response = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_200_OK
    user_list = response.json()
    assert isinstance(user_list, list)
    assert len(user_list) >= len(test_users_and_tokens["users"])
    admin_in_response = next((u for u in user_list if u['email'] == test_users_and_tokens['users']['admin']['email']), None)
    assert admin_in_response is not None
    assert "id" in admin_in_response
    assert "email" in admin_in_response
    assert "username" in admin_in_response
    assert "role" in admin_in_response
    assert "hashed_password" not in admin_in_response

@pytest.mark.asyncio
async def test_get_users_forbidden_hr(client, hr_token, test_db): # Added test_db
    """Test HR user cannot access the admin user list."""
    response = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {hr_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_get_users_forbidden_candidate(client, candidate_token, test_db): # Added test_db
    """Test Candidate user cannot access the admin user list."""
    response = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {candidate_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_403_FORBIDDEN

# --- Tests for GET /admin/stats ---

@pytest.mark.asyncio
async def test_get_stats_by_admin(client, admin_token, test_users_and_tokens, test_db: AsyncIOMotorClient): # Added test_db and type hint
    """Test admin successfully fetching system stats."""
    # Add some interview data using the injected test_db
    interviews_collection = test_db[settings.MONGODB_COLLECTION_INTERVIEWS] # Use test_db
    await interviews_collection.insert_many([
        {"interview_id": "stat_int_1", "status": "scheduled", "candidate_id": ObjectId()},
        {"interview_id": "stat_int_2", "status": "completed", "candidate_id": ObjectId()},
    ])

    response = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_200_OK
    stats = response.json()
    assert isinstance(stats, dict)
    assert "total_users" in stats
    assert "total_interviews_scheduled" in stats
    assert "total_interviews_completed" in stats
    assert "llm_service_status" in stats
    # Check values based on fixture + added data
    # Note: test_users_and_tokens fixture runs per function, so DB starts clean
    assert stats["total_users"] == len(test_users_and_tokens["users"])
    assert stats["total_interviews_scheduled"] == 2 # Based on inserted data
    assert stats["total_interviews_completed"] == 1 # Based on inserted data

@pytest.mark.asyncio
async def test_get_stats_forbidden_hr(client, hr_token, test_db): # Added test_db
    """Test HR user cannot access system stats."""
    response = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {hr_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_get_stats_forbidden_candidate(client, candidate_token, test_db): # Added test_db
    """Test Candidate user cannot access system stats."""
    response = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {candidate_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_403_FORBIDDEN

# --- Tests for DELETE /admin/users/{user_id} ---

@pytest.mark.asyncio
async def test_delete_user_by_admin_success(client, admin_token, candidate_user, test_db: AsyncIOMotorClient): # Added test_db and type hint
    """Test admin successfully deleting another user."""
    user_id_to_delete = candidate_user["id"]
    users_collection = test_db[settings.MONGODB_COLLECTION_USERS] # Use test_db

    # Verify user exists before deletion
    user_before = await users_collection.find_one({"_id": ObjectId(user_id_to_delete)})
    assert user_before is not None

    # Perform deletion
    response = client.delete(f"/api/v1/admin/users/{user_id_to_delete}", headers={"Authorization": f"Bearer {admin_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify user is deleted from DB
    user_after = await users_collection.find_one({"_id": ObjectId(user_id_to_delete)})
    assert user_after is None

@pytest.mark.asyncio
async def test_delete_user_self_deletion_forbidden(client, admin_token, admin_user, test_db): # Added test_db
    """Test admin cannot delete their own account."""
    admin_id_str = admin_user["id"]

    response = client.delete(f"/api/v1/admin/users/{admin_id_str}", headers={"Authorization": f"Bearer {admin_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "cannot delete their own account" in response.json()["detail"]

@pytest.mark.asyncio
async def test_delete_user_not_found(client, admin_token, test_db): # Added test_db
    """Test deleting a user ID that does not exist."""
    non_existent_id = str(ObjectId()) # Generate a valid but non-existent ObjectId
    response = client.delete(f"/api/v1/admin/users/{non_existent_id}", headers={"Authorization": f"Bearer {admin_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_delete_user_invalid_id_format(client, admin_token, test_db): # Added test_db
    """Test deleting using an invalid ID format."""
    invalid_id = "this-is-not-an-objectid"
    response = client.delete(f"/api/v1/admin/users/{invalid_id}", headers={"Authorization": f"Bearer {admin_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    # The ObjectId validation happens before the DB connection is even checked in the endpoint
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid ID format" in response.json()["detail"]

@pytest.mark.asyncio
async def test_delete_user_forbidden_hr(client, hr_token, candidate_user, test_db): # Added test_db
    """Test HR user cannot delete users."""
    user_id_to_delete = candidate_user["id"]
    response = client.delete(f"/api/v1/admin/users/{user_id_to_delete}", headers={"Authorization": f"Bearer {hr_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_delete_user_forbidden_candidate(client, candidate_token, hr_user, test_db): # Added test_db
    """Test Candidate user cannot delete users."""
    user_id_to_delete = hr_user["id"] # Candidate trying to delete HR user
    response = client.delete(f"/api/v1/admin/users/{user_id_to_delete}", headers={"Authorization": f"Bearer {candidate_token}"})
    # Assertion now depends on the test_db fixture working correctly via dependency override
    assert response.status_code == status.HTTP_403_FORBIDDEN