# LLM_interviewer/server/tests/test_auth.py

import pytest
from fastapi import status
from httpx import AsyncClient # Import AsyncClient for type hint

# Removed direct import of verify_token
# from app.core.security import get_password_hash # Keep if needed elsewhere

# Removed direct db import if using test_db fixture
# from app.db.mongodb import mongodb
from app.core.config import settings
from motor.motor_asyncio import AsyncIOMotorDatabase # Import for type hint

# Fixtures from conftest: client, test_db, test_users_and_tokens, ...

# --- Test Cases ---

@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient, test_db: AsyncIOMotorDatabase):
    """Test successful user registration."""
    user_data = {
        "username": "newuser_reg_succ",
        "email": "new_reg_succ@example.com",
        "password": "newpassword123",
        "role": "candidate"
    }
    users_collection = test_db[settings.MONGODB_COLLECTION_USERS]

    # PRE-CHECK
    user_before = await users_collection.find_one({"email": user_data["email"]})
    assert user_before is None, f"User {user_data['email']} already exists before registration attempt."

    response = await client.post(f"{settings.API_V1_STR}/auth/register", json=user_data)

    assert response.status_code == status.HTTP_201_CREATED, f"Registration failed unexpectedly: {response.text}"

    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["username"] == user_data["username"]
    assert data["role"] == user_data["role"]
    assert "id" in data or "_id" in data
    assert "hashed_password" not in data

    # Verify user exists in the test DB
    user_in_db = await users_collection.find_one({"email": user_data["email"]})
    assert user_in_db is not None
    assert user_in_db["username"] == user_data["username"]


@pytest.mark.asyncio
async def test_register_user_duplicate_email(client: AsyncClient, candidate_user):
    """Test registration with an email that already exists."""
    response = await client.post(f"{settings.API_V1_STR}/auth/register", json={
        "username": "anotheruser_dup_email",
        "email": candidate_user["email"], # Use existing email
        "password": "newpassword123",
        "role": "candidate"
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_register_user_duplicate_username(client: AsyncClient, candidate_user):
    """Test registration with a username that already exists."""
    response = await client.post(f"{settings.API_V1_STR}/auth/register", json={
        "username": candidate_user["username"], # Use existing username
        "email": "unique_dup_user@example.com",
        "password": "newpassword123",
        "role": "candidate"
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # This assertion failed in logs, check registration logic or fixture setup if it fails again
    assert "Username already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_register_user_invalid_role(client: AsyncClient):
    """Test registration with an invalid role."""
    response = await client.post(f"{settings.API_V1_STR}/auth/register", json={
        "username": "invalidroleuser",
        "email": "invalid_role@example.com",
        "password": "newpassword123",
        "role": "super_admin" # Invalid role
    })
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # Pydantic v2 validation error structure check
    details = response.json()["detail"]
    assert isinstance(details, list) and len(details) > 0
    assert any(err["loc"] == ["body", "role"] and "Invalid role 'super_admin'" in err["msg"] for err in details)


@pytest.mark.asyncio
async def test_login_user_success_with_email(client: AsyncClient, candidate_user):
    """Test successful login using EMAIL."""
    login_data = {
        "username": candidate_user["email"], # Use EMAIL here
        "password": candidate_user["password"]
    }
    login_response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert login_response.status_code == status.HTTP_200_OK, f"Login failed: {login_response.text}"
    login_data_resp = login_response.json()
    assert "access_token" in login_data_resp
    token = login_data_resp["access_token"]

    # Verify token works with /me
    me_response = await client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == status.HTTP_200_OK
    me_data = me_response.json()
    assert me_data["email"] == candidate_user["email"]

# --- NEW TEST ---
@pytest.mark.asyncio
async def test_login_user_success_with_username(client: AsyncClient, candidate_user):
    """Test successful login using USERNAME."""
    login_data = {
        "username": candidate_user["username"], # Use USERNAME here
        "password": candidate_user["password"]
    }
    login_response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert login_response.status_code == status.HTTP_200_OK, f"Login failed: {login_response.text}"
    login_data_resp = login_response.json()
    assert "access_token" in login_data_resp
    token = login_data_resp["access_token"]

    # Verify token works with /me
    me_response = await client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_response.status_code == status.HTTP_200_OK
    me_data = me_response.json()
    # The /me endpoint returns the full user profile, check email is correct
    assert me_data["email"] == candidate_user["email"]
    assert me_data["username"] == candidate_user["username"]
# --- END NEW TEST ---

@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, candidate_user):
    """Test login with incorrect password (using email as identifier)."""
    login_data = { "username": candidate_user["email"], "password": "wrongpassword" }
    response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    # --- UPDATED ASSERTION for error message ---
    assert "Incorrect login credentials" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_invalid_identifier(client: AsyncClient): # Renamed test
    """Test login with non-existent email/username."""
    login_data = { "username": "nosuchuser@example.com", "password": "testpassword123" }
    response = await client.post(
        f"{settings.API_V1_STR}/auth/login",
        data=login_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    # --- UPDATED ASSERTION for error message ---
    assert "Incorrect login credentials" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_current_user_me_success(client: AsyncClient, candidate_token, candidate_user):
    """Test fetching current user details (/me) with a valid token."""
    response = await client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    assert response.status_code == status.HTTP_200_OK, f"/me failed: {response.text}"
    data = response.json()
    assert data["email"] == candidate_user["email"]
    assert data["username"] == candidate_user["username"]
    assert data["role"] == candidate_user["role"]
    response_id = data.get("id") or data.get("_id")
    assert response_id == candidate_user["id"] # String vs String comparison

@pytest.mark.asyncio
async def test_get_current_user_me_no_token(client: AsyncClient):
    """Test fetching current user (/me) without providing a token."""
    response = await client.get(f"{settings.API_V1_STR}/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Not authenticated" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_current_user_me_invalid_token(client: AsyncClient):
    """Test fetching current user (/me) with an invalid/malformed token."""
    invalid_token = "this.is.not.a.valid.token"
    response = await client.get(
        f"{settings.API_V1_STR}/auth/me",
        headers={"Authorization": f"Bearer {invalid_token}"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in response.json()["detail"]

@pytest.mark.asyncio
async def test_access_protected_route_candidate(client: AsyncClient, candidate_token):
    """Test candidate accessing a route they ARE allowed to access."""
    # Example: Candidate accessing their own profile
    response = await client.get(
        f"{settings.API_V1_STR}/candidate/profile",
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.asyncio
async def test_access_protected_route_candidate_denied(client: AsyncClient, candidate_token):
    """Test candidate accessing a route they ARE NOT allowed to access."""
    # Example: Candidate trying to access admin user list
    response = await client.get(
        f"{settings.API_V1_STR}/admin/users",
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN