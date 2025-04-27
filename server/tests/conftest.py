# LLM_interviewer/server/tests/conftest.py

import pytest
import pytest_asyncio
import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional # Added Optional
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone
import uuid # Added import for uuid

# Use httpx.AsyncClient directly for async testing
from httpx import ASGITransport, AsyncClient
# Use asgi-lifespan to manage startup/shutdown
from asgi_lifespan import LifespanManager

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorClient
from bson import ObjectId

# Import application and core components
from app.main import app # Import the app instance
from app.db.mongodb import mongodb
from app.core.config import settings
from app.core.security import get_password_hash, create_access_token
from app.services.gemini_service import gemini_service, GeminiService, GeminiServiceError # Import Class too
# Import schema for EmbeddedQuestion to avoid _id issues if we use it
from app.schemas.interview import QuestionBase # Assuming QuestionBase is appropriate

# --- Logger Setup ---
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


# --- Centralized App/Client/DB Fixture using httpx.AsyncClient ---
@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Creates an httpx.AsyncClient instance configured for the FastAPI app,
    manages the app lifespan (startup/shutdown), and applies DB overrides.
    DB CLEANING IS MOVED TO test_db fixture.
    """
    test_db_name = f"{settings.MONGODB_DB}_test"
    logger.info(f"Setting up test client and DB override for: {test_db_name}")

    original_testing_mode = settings.TESTING_MODE
    settings.TESTING_MODE = True
    logger.info("Set settings.TESTING_MODE = True")

    original_override = app.dependency_overrides.get(mongodb.get_db)
    db_client_instance: Optional[AsyncIOMotorClient] = None

    try:
        # Manage application lifespan (connects DB via singleton)
        async with LifespanManager(app):
            # Verify connection post-lifespan (optional but good sanity check)
            if mongodb.client is None or mongodb.db is None:
                 logger.error("MongoDB singleton not connected after LifespanManager startup.")
                 pytest.fail("MongoDB singleton not connected after LifespanManager startup.")

            db_client_instance = mongodb.client
            logger.info(f"App lifespan started. MongoDB client connected: {db_client_instance}")

            # Prepare the test database override function
            test_db_instance = db_client_instance[test_db_name]
            def get_test_db_override() -> AsyncIOMotorDatabase:
                if db_client_instance is None:
                     raise RuntimeError("Test DB override called but db_client_instance is None.")
                # logger.debug(f"Dependency override returning test DB: {test_db_instance.name}") # Optional: verbose logging
                return test_db_instance # Return the specific instance for the override

            # Apply the override
            app.dependency_overrides[mongodb.get_db] = get_test_db_override
            logger.debug(f"Applied mongodb.get_db override for '{test_db_name}'.")

            # Yield the test client
            logger.debug("Creating and yielding AsyncClient...")
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
                yield async_client
            logger.debug("AsyncClient context exited.")

    except Exception as e:
         logger.error(f"Error during client fixture setup/lifespan: {e}", exc_info=True)
         pytest.fail(f"Client fixture failed: {e}")
    finally:
        # Restore overrides and settings
        if original_override:
            app.dependency_overrides[mongodb.get_db] = original_override
            logger.debug("Restored original mongodb.get_db override.")
        else:
            if mongodb.get_db in app.dependency_overrides:
                del app.dependency_overrides[mongodb.get_db]
                logger.debug("Removed mongodb.get_db override.")

        settings.TESTING_MODE = original_testing_mode
        logger.info(f"Restored settings.TESTING_MODE = {original_testing_mode}")
        # LifespanManager handles app shutdown and DB closing via mongodb.close()

    logger.debug("Client fixture teardown complete.")


@pytest_asyncio.fixture(scope="function")
async def test_db(client: AsyncClient) -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    Provides direct access to the test database instance AFTER the client fixture
    has run (ensuring DB override is active) and CLEANS the database by DROPPING
    collections BEFORE yielding.
    """
    if mongodb.client is None:
        pytest.fail("MongoDB client is None in test_db fixture; client fixture likely failed.")

    test_db_name = f"{settings.MONGODB_DB}_test"
    db = mongodb.client[test_db_name]
    logger.info(f"--- test_db fixture: DROPPING collections in {db.name} ---") # Log change

    collections_to_drop = [
        settings.MONGODB_COLLECTION_USERS,
        settings.MONGODB_COLLECTION_INTERVIEWS,
        settings.MONGODB_COLLECTION_RESPONSES,
        settings.MONGODB_COLLECTION_QUESTIONS
    ]
    try:
        # Drop collections instead of deleting documents
        for coll_name in collections_to_drop:
            logger.info(f"Attempting to drop collection '{coll_name}'...")
            try:
                # drop_collection works even if the collection doesn't exist
                await db.drop_collection(coll_name)
                logger.info(f"Dropped collection '{coll_name}' (or it didn't exist).")
            except Exception as drop_exc:
                # Log specific errors during drop, but maybe don't fail the whole suite?
                logger.error(f"Error dropping collection {coll_name}: {drop_exc}", exc_info=True)
                
                # Consider if this should be fatal: pytest.fail(...)

        # Optional: Add a tiny sleep just in case drop operations need a moment
        logger.info("Adding small delay after dropping collections...")
        await asyncio.sleep(0.1)
        # await asyncio.sleep(0.05)

        logger.info(f"--- test_db fixture: Yielding database (collections will be auto-created): {db.name} ---")
        yield db # Yield the database instance for the test function
        logger.info(f"--- test_db fixture: Teardown for {db.name} ---")
        # No cleanup needed after yield if we drop before the test

    except Exception as e:
        logger.error(f"Error during test_db fixture setup/drop: {e}", exc_info=True)
        pytest.fail(f"test_db fixture failed during dropping collections: {e}")


@pytest_asyncio.fixture(scope="function")
async def test_users_and_tokens(test_db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    Populates the CLEAN test DB (provided by test_db fixture) with users
    and generates tokens. Depends on test_db to ensure cleaning happened first.
    """
    db = test_db # Use the cleaned DB provided by the dependency
    # Collection will be implicitly created by MongoDB/Motor on first insert
    users_collection = db[settings.MONGODB_COLLECTION_USERS]
    users_data = [
        {"email": "hr@example.com", "username": "hruser", "role": "hr", "password": "testpassword123"},
        {"email": "candidate@example.com", "username": "candidateuser", "role": "candidate", "password": "testpassword123"},
        {"email": "admin@example.com", "username": "adminuser", "role": "admin", "password": "testpassword123"},
    ]
    users_created = {}
    tokens = {}
    object_ids = {}
    utc_now = datetime.now(timezone.utc)

    logger.debug(f"Populating test users in CLEAN DB: {db.name}/{users_collection.name}")
    for user_info in users_data:
        user_doc_to_insert = {
            "username": user_info["username"],
            "email": user_info["email"],
            "hashed_password": get_password_hash(user_info["password"]),
            "role": user_info["role"],
            "created_at": utc_now,
            "updated_at": utc_now,
            "resume_path": None,
            "resume_text": None,
        }
        try:
            # Insert user
            insert_result = await users_collection.insert_one(user_doc_to_insert)
            inserted_id = insert_result.inserted_id
            # Fetch immediately after insert to get the definitive document state
            retrieved_doc = await users_collection.find_one({"_id": inserted_id})
            if not retrieved_doc:
                 pytest.fail(f"Failed to retrieve user {user_info['email']} immediately after insert.")

            logger.debug(f"Inserted user: {user_info['email']} with ID: {inserted_id}")

            user_id_str = str(retrieved_doc["_id"])
            # Store the retrieved data, including the correct ObjectId and its string representation
            user_data_for_fixture = {
                "id": user_id_str, # String ID for comparisons in tests/path params
                "_id": retrieved_doc["_id"], # ObjectId for direct DB operations in tests
                "username": retrieved_doc["username"],
                "email": retrieved_doc["email"],
                "role": retrieved_doc["role"],
                "password": user_info["password"], # Store plain password for login tests
            }
            users_created[user_info["role"]] = user_data_for_fixture
            tokens[user_info["role"]] = create_access_token(data={"sub": retrieved_doc["email"], "role": retrieved_doc["role"]})
            object_ids[user_info["role"]] = retrieved_doc["_id"] # Store ObjectId

        except Exception as e:
            pytest.fail(f"Failed to insert/retrieve user {user_info['email']} in test_users_and_tokens fixture: {e}")

    user_count = await users_collection.count_documents({})
    logger.debug(f"Finished populating test users. Total users in collection: {user_count}")
    if user_count != len(users_data):
        logger.warning(f"Expected {len(users_data)} users after population, but found {user_count}. Check for interference.")

    return {"users": users_created, "tokens": tokens, "ids": object_ids}

# --- Individual User/Token Fixtures (Depend on test_users_and_tokens) ---
@pytest.fixture(scope="function")
def admin_token(test_users_and_tokens: Dict[str, Any]): return test_users_and_tokens["tokens"]["admin"]
@pytest.fixture(scope="function")
def hr_token(test_users_and_tokens: Dict[str, Any]): return test_users_and_tokens["tokens"]["hr"]
@pytest.fixture(scope="function")
def candidate_token(test_users_and_tokens: Dict[str, Any]): return test_users_and_tokens["tokens"]["candidate"]
@pytest.fixture(scope="function")
def candidate_user(test_users_and_tokens: Dict[str, Any]): return test_users_and_tokens["users"]["candidate"]
@pytest.fixture(scope="function")
def hr_user(test_users_and_tokens: Dict[str, Any]): return test_users_and_tokens["users"]["hr"]
@pytest.fixture(scope="function")
def admin_user(test_users_and_tokens: Dict[str, Any]): return test_users_and_tokens["users"]["admin"]
@pytest.fixture(scope="function")
def candidate_object_id(test_users_and_tokens: Dict[str, Any]): return test_users_and_tokens["ids"]["candidate"]


# --- Mock Gemini Fixture ---
@pytest_asyncio.fixture(scope="function", autouse=True)
async def mock_gemini():
    """Mocks the Gemini service calls."""
    mock_gen_response = MagicMock()
    # Ensure mock data provides fields needed by schema (e.g., QuestionBase)
    mock_data = [
        {"text": "Mock Q1?", "category": "Mock", "difficulty": "Easy", "question_id": str(uuid.uuid4())},
        {"text": "Mock Q2?", "category": "Mock", "difficulty": "Medium", "question_id": str(uuid.uuid4())}
    ]
    mock_gen_response.text = json.dumps(mock_data)
    mock_gen_response.prompt_feedback = None # Simulate successful response

    mock_eval_response = MagicMock()
    mock_eval_response.text = json.dumps({ "score": 3.5, "feedback": "[AI]: Mock evaluation." })
    mock_eval_response.prompt_feedback = None # Simulate successful response

    async def mock_generate_content_side_effect(*args, **kwargs):
        prompt = args[0] if args else ""
        if isinstance(prompt, list): prompt = " ".join(str(p) for p in prompt)

        if "evaluate" in prompt.lower():
            logger.debug("Mock Gemini: Returning evaluation response.")
            return mock_eval_response
        else:
            logger.debug("Mock Gemini: Returning question generation response.")
            return mock_gen_response

    # Check if gemini_service and its model attribute are properly initialized
    gemini_model_exists = hasattr(gemini_service, 'model') and gemini_service.model is not None
    mock_target = None
    patcher = None
    patcher_gen = None # Define patcher variables outside conditional scope
    patcher_eval = None

    if gemini_model_exists:
        # If the model exists, patch its generate_content_async method
        logger.debug("Patching gemini_service.model.generate_content_async")
        mock_target = 'app.services.gemini_service.gemini_service.model.generate_content_async'
        patcher = patch(mock_target, new_callable=AsyncMock, side_effect=mock_generate_content_side_effect)
    else:
        # If model doesn't exist, patch the service methods directly
        logger.warning("Gemini model not found/initialized. Patching service methods directly.")
        async def mock_gen_q(*args, **kwargs): return json.loads(mock_gen_response.text)
        async def mock_eval_a(*args, **kwargs): return json.loads(mock_eval_response.text)
        patcher_gen = patch('app.services.gemini_service.gemini_service.generate_questions', new=mock_gen_q)
        patcher_eval = patch('app.services.gemini_service.gemini_service.evaluate_answer', new=mock_eval_a)

    # Use try/finally to ensure patchers are stopped
    try:
        mock_result = None
        if patcher: # Patching model method
            mock_result = patcher.start()
        elif patcher_gen and patcher_eval: # Patching service methods
            mock_gen = patcher_gen.start()
            mock_eval = patcher_eval.start()
            mock_result = (mock_gen, mock_eval) # Yield tuple of mocks

        yield mock_result # Yield the mock(s) for potential assertions in tests

    finally:
        # Stop the active patchers
        if patcher and patcher.is_local:
            patcher.stop()
            logger.debug(f"Stopped patching {mock_target}")
        if patcher_gen and patcher_gen.is_local:
            patcher_gen.stop()
            logger.debug("Stopped patching gemini_service.generate_questions")
        if patcher_eval and patcher_eval.is_local:
            patcher_eval.stop()
            logger.debug("Stopped patching gemini_service.evaluate_answer")