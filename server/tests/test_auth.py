import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_password_hash
from app.db.mongodb import mongodb

client = TestClient(app)

@pytest.fixture(autouse=True)
async def clear_db():
    # Clear users collection before each test
    await mongodb.client.llminterview.users.delete_many({})
    yield

@pytest.mark.asyncio
async def test_register_user():
    response = client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword123",
        "role": "candidate"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "candidate"
    assert "password" not in data

@pytest.mark.asyncio
async def test_login_user():
    # First register a user
    await mongodb.client.llminterview.users.insert_one({
        "username": "testuser",
        "email": "test@example.com",
        "hashed_password": get_password_hash("testpassword123"),
        "role": "candidate"
    })
    
    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials():
    response = client.post("/auth/login", json={
        "email": "wrong@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401 