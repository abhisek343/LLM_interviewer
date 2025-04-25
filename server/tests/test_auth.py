# LLM_interviewer/server/tests/test_auth.py

import pytest
from fastapi import status
# from fastapi.testclient import TestClient # Now using client fixture from conftest
# from app.main import app # App is used via client fixture
# Import security functions used directly in tests if any, or for verification
from app.core.security import get_password_hash, create_access_token, verify_token # Changed decode_access_token to verify_token
from app.db.mongodb import mongodb # Import the singleton instance
from app.core.config import settings # Import settings instance directly
from datetime import datetime, timedelta
from bson import ObjectId

# Fixtures like client, test_users_and_tokens, admin_token, hr_token, candidate_token, candidate_user, etc.
# are now expected to be provided by conftest.py

# --- Fixtures specific to this file are removed as they are consolidated in conftest.py ---
# @pytest.fixture(scope="module")
# async def test_user(): ... (REMOVED)

# @pytest.fixture
# def test_user_token(test_user): ... (REMOVED)

# --- Test Cases ---

@pytest.mark.asyncio
async def test_register_user_success(client): # Use client fixture
    """Test successful user registration."""
    response = client.post("/api/v1/auth/register", json={ # Added /api/v1 prefix
        "username": "newuser",
        "email": "new@example.com",
        "password": "newpassword123",
        "role": "candidate" # Explicitly setting role
    })
    # Assuming register returns UserOut model now
    assert response.status_code == status.HTTP_201_CREATED # Check for 201
    data = response.json()
    assert data["email"] == "new@example.com"
    assert data["username"] == "newuser"
    assert data["role"] == "candidate"
    assert "hashed_password" not in data # Ensure password isn't returned
    assert "id" in data # Ensure user ID is returned

    # Verify user exists in DB
    db = mongodb.client[settings.MONGODB_DB + "_test"] # Use test DB
    user_in_db = await db[settings.MONGODB_COLLECTION_USERS].find_one({"email": "new@example.com"})
    assert user_in_db is not None
    assert user_in_db["username"] == "newuser"

@pytest.mark.asyncio
async def test_register_user_duplicate_email(client, candidate_user): # Use existing user fixture
    """Test registration with an email that already exists."""
    response = client.post("/api/v1/auth/register", json={ # Added /api/v1 prefix
        "username": "anotheruser",
        "email": candidate_user["email"], # Use existing email from fixture
        "password": "newpassword123",
        "role": "candidate"
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_register_user_duplicate_username(client, candidate_user): # Use existing user fixture
    """Test registration with a username that already exists."""
    response = client.post("/api/v1/auth/register", json={ # Added /api/v1 prefix
        "username": candidate_user["username"], # Use existing username from fixture
        "email": "unique@example.com",
        "password": "newpassword123",
        "role": "candidate"
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Username already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_register_user_invalid_role(client):
    """Test registration with an invalid role."""
    response = client.post("/api/v1/auth/register", json={ # Added /api/v1 prefix
        "username": "invalidroleuser",
        "email": "invalid@example.com",
        "password": "newpassword123",
        "role": "super_admin" # Not a valid role ('candidate', 'hr', 'admin')
    })
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Validation error
    # Pydantic v2 error message format might differ slightly
    assert "Input should be 'admin', 'hr' or 'candidate'" in response.text or "value is not a valid enumeration member" in response.text

@pytest.mark.asyncio
async def test_login_user_success(client, candidate_user): # Use existing user fixture
    """Test successful login with correct credentials."""
    login_data = {
        # FastAPI's OAuth2PasswordRequestForm expects 'username' and 'password'
        "username": candidate_user["email"],
        "password": candidate_user["password"] # Use password stored in fixture
    }
    # Send as form data
    response = client.post(
        "/api/v1/auth/login", # Added /api/v1 prefix
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"} # Correct content type
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Optionally decode token to verify contents
    token = data["access_token"]
    payload = verify_token(token) # Use verify_token instead of decode_access_token
    assert payload is not None
    assert payload.get("sub") == candidate_user["email"]
    assert payload.get("role") == candidate_user["role"]
    # assert payload.get("id") == candidate_user["id"] # Verify ID if included in token creation

@pytest.mark.asyncio
async def test_login_invalid_password(client, candidate_user): # Use existing user fixture
    """Test login with incorrect password."""
    login_data = { "username": candidate_user["email"], "password": "wrongpassword" }
    response = client.post( "/api/v1/auth/login", data=login_data, headers={"Content-Type": "application/x-www-form-urlencoded"} ) # Added /api/v1 prefix
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect email or password" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_invalid_email(client):
    """Test login with non-existent email."""
    login_data = { "username": "nosuchuser@example.com", "password": "testpassword123" }
    response = client.post( "/api/v1/auth/login", data=login_data, headers={"Content-Type": "application/x-www-form-urlencoded"} ) # Added /api/v1 prefix
    assert response.status_code == status.HTTP_401_UNAUTHORIZED # Should be 401 if user not found
    assert "Incorrect email or password" in response.json()["detail"] # Same generic error

@pytest.mark.asyncio
async def test_get_current_user_me_success(client, candidate_token, candidate_user):
    """Test fetching current user details (/me) with a valid token."""
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {candidate_token}"}) # Added /api/v1 prefix
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == candidate_user["email"]
    assert data["username"] == candidate_user["username"]
    assert data["role"] == candidate_user["role"]
    assert "hashed_password" not in data
    assert data["id"] == candidate_user["id"]

@pytest.mark.asyncio
async def test_get_current_user_me_no_token(client):
    """Test fetching current user (/me) without providing a token."""
    response = client.get("/api/v1/auth/me") # Added /api/v1 prefix
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Not authenticated" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_current_user_me_invalid_token(client):
    """Test fetching current user (/me) with an invalid/malformed token."""
    invalid_token = "this.is.not.a.valid.token"
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {invalid_token}"}) # Added /api/v1 prefix
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    # Detail might vary based on JWT error, check for common credential issue
    assert "Could not validate credentials" in response.json()["detail"]

@pytest.mark.asyncio
async def test_access_protected_route_candidate(client, candidate_token):
    """Test candidate accessing a route they ARE allowed to access."""
    # Use /candidate/profile as an example candidate route
    response = client.get("/api/v1/candidate/profile", headers={"Authorization": f"Bearer {candidate_token}"}) # Added /api/v1 prefix
    # Should succeed
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.asyncio
async def test_access_protected_route_candidate_denied(client, candidate_token):
    """Test candidate accessing a route they ARE NOT allowed to access."""
    # Use /admin/users as an example admin-only route
    response = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {candidate_token}"}) # Added /api/v1 prefix
    # Should be forbidden
    assert response.status_code == status.HTTP_403_FORBIDDEN