# LLM_interviewer/server/tests/conftest.py

import os
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from unittest.mock import patch, AsyncMock, MagicMock
import json
import logging
from fastapi import FastAPI
from dotenv import load_dotenv
import asyncio
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_db
from app.db.mongodb import mongodb, MongoDB
from app.core.config import settings
from app.services.gemini_service import gemini_service
from bson import ObjectId
from datetime import datetime
from app.core.security import get_password_hash, create_access_token

# Load test environment variables
load_dotenv('.env.test')

from app.api.routes import auth, candidates, interview, admin

# --- Logger Setup ---
logger = logging.getLogger(__name__)

# --- Event Loop Management ---
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# --- Test Client Fixture ---
@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c

# --- MongoDB Fixture & Dependency Override (REVISED) ---
@pytest_asyncio.fixture(scope="function", autouse=True)
async def test_db_setup_and_override():
    """
    Connects main singleton to DB, clears TEST DB, sets up override, yields, cleans up override.
    Relies on app lifespan to manage main connection closing.
    """
    test_db_name = f"{settings.MONGODB_DB}_test"
    test_mongo_url = settings.MONGODB_URL

    if not test_mongo_url or not test_db_name:
        pytest.fail("MONGODB_URL or MONGODB_DB not configured for tests.")

    # Ensure the main singleton connects
    if not mongodb.client:
        logger.warning("MongoDB singleton client not connected before test setup. Attempting connect.")
        await mongodb.connect()

    test_db_client = mongodb.client
    if not test_db_client:
        await mongodb.close()
        pytest.fail("Failed to get MongoDB client from singleton after connect(). Check lifespan/connection logic.")

    db_instance_for_test: AsyncIOMotorDatabase = test_db_client[test_db_name]

    # Clear test database before yielding
    try:
        collections = await db_instance_for_test.list_collection_names()
        for collection_name in collections:
            if not collection_name.startswith('system.'):
                await db_instance_for_test[collection_name].delete_many({})
    except Exception as e:
        pytest.fail(f"Failed to clear test MongoDB ({test_db_name}): {e}")

    # --- Define override ---
    def override_get_db_dependency() -> AsyncIOMotorDatabase:
        if mongodb.client is None:
            raise RuntimeError("MongoDB singleton not connected during dependency override.")
        return mongodb.client[test_db_name]

    # Apply override BEFORE yielding
    original_override = app.dependency_overrides.get(mongodb.get_db)
    app.dependency_overrides[mongodb.get_db] = override_get_db_dependency

    yield db_instance_for_test

    # --- Teardown ---
    if original_override:
        app.dependency_overrides[mongodb.get_db] = original_override
    else:
        if mongodb.get_db in app.dependency_overrides:
            del app.dependency_overrides[mongodb.get_db]

# --- User and Token Fixtures (Updated to use test_db_setup_and_override) ---
@pytest_asyncio.fixture(scope="function")
async def test_users_and_tokens(test_db_setup_and_override):
    db = test_db_setup_and_override
    users_collection = db[settings.MONGODB_COLLECTION_USERS]
    users_data = [
        {"email": "hr@example.com", "username": "hruser", "role": "hr", "password": "testpassword123"},
        {"email": "candidate@example.com", "username": "candidateuser", "role": "candidate", "password": "testpassword123"},
        {"email": "admin@example.com", "username": "adminuser", "role": "admin", "password": "testpassword123"},
    ]
    users_created = {}
    tokens = {}
    object_ids = {}

    for user_info in users_data:
        user_doc = {
            "_id": ObjectId(),
            "username": user_info["username"],
            "email": user_info["email"],
            "hashed_password": get_password_hash(user_info["password"]),
            "role": user_info["role"],
            "created_at": datetime.utcnow(),
            "resume_path": None,
            "resume_text": None,
        }
        original_password = user_info["password"]
        insert_result = await users_collection.insert_one(user_doc)
        user_id_str = str(insert_result.inserted_id)
        user_data_for_fixture = {
            "id": user_id_str,
            "username": user_info["username"],
            "email": user_info["email"],
            "role": user_info["role"],
            "password": original_password,
            "_id": insert_result.inserted_id
        }
        users_created[user_info["role"]] = user_data_for_fixture
        tokens[user_info["role"]] = create_access_token(data={"sub": user_info["email"], "role": user_info["role"]})
        object_ids[user_info["role"]] = insert_result.inserted_id

    return {"users": users_created, "tokens": tokens, "ids": object_ids}

# --- Individual Fixtures (Keep as is) ---
@pytest.fixture
def admin_token(test_users_and_tokens): return test_users_and_tokens["tokens"]["admin"]
@pytest.fixture
def hr_token(test_users_and_tokens): return test_users_and_tokens["tokens"]["hr"]
@pytest.fixture
def candidate_token(test_users_and_tokens): return test_users_and_tokens["tokens"]["candidate"]
@pytest.fixture
def candidate_user(test_users_and_tokens): return test_users_and_tokens["users"]["candidate"]
@pytest.fixture
def hr_user(test_users_and_tokens): return test_users_and_tokens["users"]["hr"]
@pytest.fixture
def admin_user(test_users_and_tokens): return test_users_and_tokens["users"]["admin"]
@pytest.fixture
def candidate_object_id(test_users_and_tokens): return test_users_and_tokens["ids"]["candidate"]

# --- Mock Gemini Fixture (Updated with valid JSON) ---
@pytest_asyncio.fixture(autouse=True)
async def mock_gemini():
    mock_gen_response = MagicMock()
    mock_gen_response.text = json.dumps([
        {
            "text": "Mock Q1?",
            "category": "Mock",
            "difficulty": "Easy",
            "question_id": "mock-id-1",
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "text": "Mock Q2?",
            "category": "Mock",
            "difficulty": "Medium",
            "question_id": "mock-id-2",
            "created_at": datetime.utcnow().isoformat()
        }
    ])
    mock_gen_response.prompt_feedback = None

    mock_eval_response = MagicMock()
    mock_eval_response.text = json.dumps({
        "score": 3.5,
        "feedback": "[AI]: Mock evaluation."
    })
    mock_eval_response.prompt_feedback = None

    async def mock_generate_content_side_effect(*args, **kwargs):
        prompt = args[0] if args else ""
        if "evaluate" in prompt.lower():
            return mock_eval_response
        else:
            return mock_gen_response

    if not hasattr(gemini_service, 'model') or gemini_service.model is None:
        gemini_service.model = MagicMock()
        gemini_service.model.generate_content_async = AsyncMock(side_effect=mock_generate_content_side_effect)
        yield gemini_service.model.generate_content_async
    else:
        with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
                  new_callable=AsyncMock, 
                  side_effect=mock_generate_content_side_effect) as mock_api_call:
            yield mock_api_call