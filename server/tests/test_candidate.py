# LLM_interviewer/server/tests/test_candidate.py

import pytest
from fastapi import status
from app.db.mongodb import mongodb # Keep for type hints if needed
from app.core.config import settings
from unittest.mock import patch, AsyncMock, MagicMock, ANY
from bson import ObjectId
import io
import shutil
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient # Import for type hinting

# Fixtures like client, test_users_and_tokens, candidate_token, hr_token, admin_token,
# candidate_user, hr_user, test_db are provided by conftest.py

# --- Tests for GET /candidate/profile ---

@pytest.mark.asyncio
async def test_get_profile_success(client, candidate_token, candidate_user, test_db): # Added test_db
    """Test candidate successfully fetching their own profile."""
    response = client.get("/api/v1/candidate/profile", headers={"Authorization": f"Bearer {candidate_token}"})
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_200_OK
    profile = response.json()
    assert profile["id"] == candidate_user["id"]
    assert profile["username"] == candidate_user["username"]
    assert profile["email"] == candidate_user["email"]
    assert profile["role"] == "candidate"
    assert "hashed_password" not in profile

@pytest.mark.asyncio
async def test_get_profile_forbidden_hr(client, hr_token, test_db): # Added test_db
    """Test HR cannot access candidate profile endpoint."""
    response = client.get("/api/v1/candidate/profile", headers={"Authorization": f"Bearer {hr_token}"})
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_get_profile_forbidden_admin(client, admin_token, test_db): # Added test_db
    """Test Admin cannot access candidate profile endpoint."""
    response = client.get("/api/v1/candidate/profile", headers={"Authorization": f"Bearer {admin_token}"})
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_403_FORBIDDEN

# --- Tests for PUT /candidate/profile ---

@pytest.mark.asyncio
async def test_update_profile_success(client, candidate_token, candidate_user, test_db: AsyncIOMotorClient): # Added test_db
    """Test candidate successfully updating their profile (username)."""
    update_payload = {"username": "updated_candidate"}

    response = client.put(
        "/api/v1/candidate/profile",
        json=update_payload,
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_200_OK
    updated_profile = response.json()
    assert updated_profile["username"] == "updated_candidate"
    assert updated_profile["email"] == candidate_user["email"]

    # Verify DB using the test_db fixture
    user_in_db = await test_db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": ObjectId(candidate_user["id"])}) # Use test_db
    assert user_in_db is not None
    assert user_in_db["username"] == "updated_candidate"

@pytest.mark.asyncio
async def test_update_profile_username_taken(client, candidate_token, hr_user, test_db): # Added test_db
    """Test candidate trying to update username to one that already exists."""
    update_payload = {"username": hr_user["username"]}

    response = client.put(
        "/api/v1/candidate/profile",
        json=update_payload,
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Username already taken" in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_profile_no_data(client, candidate_token, test_db): # Added test_db
    """Test sending empty payload for profile update."""
    response = client.put(
        "/api/v1/candidate/profile",
        json={},
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "At least one field must be provided for update" in response.text

@pytest.mark.asyncio
async def test_update_profile_forbidden_hr(client, hr_token, test_db): # Added test_db
    """Test HR cannot update a candidate's profile via this route."""
    update_payload = {"username": "hr_updated_name"}
    response = client.put(
        "/api/v1/candidate/profile",
        json=update_payload,
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_403_FORBIDDEN

# --- Tests for POST /candidate/resume ---

@pytest.mark.asyncio
@patch('app.api.routes.candidates.Path.open')
@patch('app.api.routes.candidates.shutil.copyfileobj')
@patch('app.api.routes.candidates.Path.unlink')
@patch('app.api.routes.candidates.parse_resume', new_callable=AsyncMock)
async def test_upload_resume_success(
    mock_parse_resume, mock_unlink, mock_copyfileobj, mock_path_open,
    client, candidate_token, candidate_user, test_db: AsyncIOMotorClient # Added test_db
):
    """Test successful resume upload by candidate."""
    mock_parse_resume.return_value = "Parsed resume text content."
    mock_file_handle = MagicMock()
    mock_path_open.return_value.__enter__.return_value = mock_file_handle

    file_content = b"dummy pdf content"
    file_name = "my_resume.pdf"
    files = {'resume': (file_name, io.BytesIO(file_content), 'application/pdf')}

    response = client.post(
        "/api/v1/candidate/resume",
        files=files,
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["message"] == "Resume uploaded successfully"
    assert "file_path" in data
    assert file_name in Path(data["file_path"]).name
    assert data["parsing_status"].startswith("successfully parsed")

    mock_path_open.assert_called_once()
    mock_copyfileobj.assert_called_once_with(ANY, mock_file_handle)
    mock_parse_resume.assert_awaited_once()

    # Verify DB update using the test_db fixture
    user_doc = await test_db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": ObjectId(candidate_user["id"])}) # Use test_db
    assert user_doc is not None
    assert "resume_path" in user_doc
    assert Path(user_doc["resume_path"]).name == Path(data["file_path"]).name
    assert user_doc.get("resume_text") == "Parsed resume text content."

@pytest.mark.asyncio
async def test_upload_resume_invalid_extension(client, candidate_token, test_db): # Added test_db
    """Test uploading a file with a non-allowed extension."""
    file_content = b"dummy text content"
    file_name = "my_resume.txt"
    files = {'resume': (file_name, io.BytesIO(file_content), 'text/plain')}

    response = client.post(
        "/api/v1/candidate/resume",
        files=files,
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid file type" in response.json()["detail"]

@pytest.mark.asyncio
async def test_upload_resume_forbidden_hr(client, hr_token, test_db): # Added test_db
    """Test HR user cannot upload resume via candidate endpoint."""
    file_content = b"dummy pdf content"
    file_name = "hr_resume.pdf"
    files = {'resume': (file_name, io.BytesIO(file_content), 'application/pdf')}

    response = client.post(
        "/api/v1/candidate/resume",
        files=files,
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
@patch('app.api.routes.candidates.Path.open')
@patch('app.api.routes.candidates.shutil.copyfileobj')
@patch('app.api.routes.candidates.Path.unlink')
@patch('app.api.routes.candidates.parse_resume', new_callable=AsyncMock)
async def test_upload_resume_parser_error(
    mock_parse_resume, mock_unlink, mock_copyfileobj, mock_path_open,
    client, candidate_token, candidate_user, test_db: AsyncIOMotorClient # Added test_db
):
    """Test resume upload when the parser service returns an error."""
    mock_parse_resume.side_effect = Exception("Parsing failed badly")
    mock_file_handle = MagicMock()
    mock_path_open.return_value.__enter__.return_value = mock_file_handle

    file_content = b"dummy pdf content"
    file_name = "bad_resume.pdf"
    files = {'resume': (file_name, io.BytesIO(file_content), 'application/pdf')}

    response = client.post(
        "/api/v1/candidate/resume",
        files=files,
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    # Assertion depends on test_db fixture providing connection via override
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["message"] == "Resume uploaded successfully"
    assert "file_path" in data
    assert "parse failed" in data["parsing_status"]

    # Verify DB update using the test_db fixture
    user_doc = await test_db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": ObjectId(candidate_user["id"])}) # Use test_db
    assert user_doc is not None
    assert "resume_path" in user_doc
    assert Path(user_doc["resume_path"]).name == Path(data["file_path"]).name
    assert user_doc.get("resume_text") is None