# LLM_interviewer/server/tests/test_interview_flow.py

import pytest
from unittest.mock import patch, AsyncMock, ANY # Removed MagicMock if not used, Added ANY
from fastapi import status
# from fastapi.testclient import TestClient # Provided by fixture
# from app.main import app # Used via client fixture
# from app.core.security import get_password_hash, create_access_token # Not used directly
from app.db.mongodb import mongodb # Keep for type hinting if needed, but use test_db fixture for access
from app.core.config import settings # Use settings instance directly
from datetime import datetime, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient # Import for type hint

# Fixtures like client, test_users_and_tokens, admin_token, hr_token, candidate_token,
# candidate_user, hr_user, candidate_object_id, mock_gemini, test_db
# are now expected to be provided by conftest.py

# --- Helper Functions (No changes needed here unless they also accessed mongodb.client) ---
async def create_test_interview(client, hr_token, candidate_id_str, num_questions=2):
     """Helper to schedule an interview using the API."""
     interview_data = {
         "candidate_id": candidate_id_str,
         "scheduled_time": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
         "role": "Test Role",
         "tech_stack": ["Test"],
     }
     response = client.post("/api/v1/interview/schedule", json=interview_data, headers={"Authorization": f"Bearer {hr_token}"})
     assert response.status_code == status.HTTP_201_CREATED, f"Failed to schedule: {response.text}"
     interview = response.json()
     assert len(interview.get("questions", [])) >= num_questions
     return interview


async def submit_all_test_responses(client, candidate_token, interview, test_db: AsyncIOMotorClient): # Added test_db parameter
    """Helper to submit all responses for a given interview."""
    interview_id = interview["interview_id"]
    responses_payload = []
    if not interview or not interview.get("questions"):
         pytest.fail("Interview data or questions missing in submit_all_test_responses helper.")

    for q in interview["questions"]:
         q_id = q.get("question_id")
         if not q_id:
              pytest.fail(f"Question missing 'question_id' in interview data: {q}")
         responses_payload.append({ "question_id": q_id, "answer": f"Ans for {q_id}" })

    submission_data = {"interview_id": interview_id, "responses": responses_payload}
    response = client.post("/api/v1/interview/submit-all", json=submission_data, headers={"Authorization": f"Bearer {candidate_token}"})
    assert response.status_code == status.HTTP_200_OK, f"Failed to submit all responses: {response.text}"

    # Verify interview is now completed using the injected test_db
    interview_doc = await test_db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
    assert interview_doc is not None, f"Interview doc {interview_id} not found after submission."
    assert interview_doc.get("status") == "completed", f"Interview {interview_id} status not 'completed' after submission."


async def submit_manual_feedback(client, hr_token, interview_id, payload):
    """Helper to submit manual feedback/scores."""
    response = client.post(f"/api/v1/interview/{interview_id}/results", json=payload, headers={"Authorization": f"Bearer {hr_token}"})
    assert response.status_code == status.HTTP_200_OK, f"Failed to submit feedback: {response.text}"
    return response.json()

# --- Test Cases (Updated) ---

@pytest.mark.asyncio
async def test_get_result_no_scores(client, hr_token, candidate_token, candidate_user, test_db): # Added test_db
    # 1. Schedule and complete interview
    interview = await create_test_interview(client, hr_token, candidate_user["id"])
    interview_id = interview["interview_id"]
    await submit_all_test_responses(client, candidate_token, interview, test_db) # Pass test_db

    # 2. Fetch results (before any scoring)
    response = client.get(f"/api/v1/interview/results/{interview_id}", headers={"Authorization": f"Bearer {hr_token}"})
    assert response.status_code == status.HTTP_200_OK
    result = response.json()

    # Assert calculated score is None as no responses were scored
    assert result.get("total_score") is None
    assert "Evaluation pending" in result.get("overall_feedback", "")

@pytest.mark.asyncio
async def test_get_result_calculated_from_individual_scores(client, hr_token, candidate_token, candidate_user, candidate_object_id, test_db): # Added test_db
    # 1. Schedule and complete interview
    interview = await create_test_interview(client, hr_token, candidate_user["id"])
    interview_id = interview["interview_id"]
    await submit_all_test_responses(client, candidate_token, interview, test_db) # Pass test_db

    # 2. Manually update scores for individual responses using the test_db fixture
    responses_collection = test_db[settings.MONGODB_COLLECTION_RESPONSES] # Use test_db
    q1_id = interview["questions"][0].get("question_id", "mock_q1")
    q2_id = interview["questions"][1].get("question_id", "mock_q2")

    await responses_collection.update_one(
        {"interview_id": interview_id, "question_id": q1_id, "candidate_id": candidate_object_id},
        {"$set": {"score": 4.0}}
    )
    await responses_collection.update_one(
        {"interview_id": interview_id, "question_id": q2_id, "candidate_id": candidate_object_id},
        {"$set": {"score": 2.0}}
    )

    # 3. Fetch results and verify calculated average score
    response = client.get(f"/api/v1/interview/results/{interview_id}", headers={"Authorization": f"Bearer {hr_token}"})
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["total_score"] == pytest.approx(3.0)
    assert "Evaluation pending" not in result.get("overall_feedback", "")

@pytest.mark.asyncio
async def test_post_results_calculates_and_stores_overall_score(client, hr_token, candidate_token, candidate_user, test_db): # Added test_db
    # 1. Schedule and complete interview
    interview = await create_test_interview(client, hr_token, candidate_user["id"])
    interview_id = interview["interview_id"]
    q1_id = interview["questions"][0].get("question_id", "mock_q1")
    q2_id = interview["questions"][1].get("question_id", "mock_q2")
    await submit_all_test_responses(client, candidate_token, interview, test_db) # Pass test_db

    # 2. Submit individual scores via the results endpoint
    feedback_payload = {
        "responses_feedback": [
            {"question_id": q1_id, "score": 5.0, "feedback": "Excellent"},
            {"question_id": q2_id, "score": 3.0, "feedback": "Okay"},
        ]
    }
    await submit_manual_feedback(client, hr_token, interview_id, feedback_payload)

    # 3. Fetch results and verify calculated average score
    response = client.get(f"/api/v1/interview/results/{interview_id}", headers={"Authorization": f"Bearer {hr_token}"})
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["total_score"] == pytest.approx(4.0)

    # 4. Verify the calculated overall score was stored in the interview document
    updated_interview_doc = await test_db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id}) # Use test_db
    assert updated_interview_doc is not None
    assert updated_interview_doc.get("overall_score") == pytest.approx(4.0)
    assert updated_interview_doc.get("overall_feedback") is None
    assert updated_interview_doc.get("evaluated_by") is not None

@pytest.mark.asyncio
async def test_post_results_manual_overall_score_override(client, hr_token, candidate_token, candidate_user, test_db): # Added test_db
    # 1. Schedule and complete interview
    interview = await create_test_interview(client, hr_token, candidate_user["id"])
    interview_id = interview["interview_id"]
    q1_id = interview["questions"][0].get("question_id", "mock_q1")
    q2_id = interview["questions"][1].get("question_id", "mock_q2")
    await submit_all_test_responses(client, candidate_token, interview, test_db) # Pass test_db

    # 2. Submit individual scores AND a manual overall score
    feedback_payload = {
        "responses_feedback": [
            {"question_id": q1_id, "score": 5.0, "feedback": "Excellent"},
            {"question_id": q2_id, "score": 3.0, "feedback": "Okay"},
        ],
        "overall_score": 1.5, # Manual override score
        "overall_feedback": "Manual overall feedback provided."
    }
    await submit_manual_feedback(client, hr_token, interview_id, feedback_payload)

    # 3. Fetch results and verify the MANUALLY submitted overall score is used
    response = client.get(f"/api/v1/interview/results/{interview_id}", headers={"Authorization": f"Bearer {hr_token}"})
    assert response.status_code == status.HTTP_200_OK
    result = response.json()
    assert result["total_score"] == pytest.approx(1.5)
    assert result["overall_feedback"] == "Manual overall feedback provided."

    # 4. Verify the overridden score and feedback were stored in the interview document
    updated_interview_doc = await test_db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id}) # Use test_db
    assert updated_interview_doc is not None
    assert updated_interview_doc.get("overall_score") == pytest.approx(1.5)
    assert updated_interview_doc.get("overall_feedback") == "Manual overall feedback provided."

@pytest.mark.asyncio
# mock_gemini fixture is autouse=True in conftest.py
async def test_ai_evaluation_updates_response(client, hr_token, candidate_token, candidate_user, candidate_object_id, test_db): # Added test_db
    # 1. Create interview & submit responses
    interview = await create_test_interview(client, hr_token, candidate_user["id"])
    interview_id = interview["interview_id"]
    q1_id = interview["questions"][0].get("question_id", "mock_q1")
    await submit_all_test_responses(client, candidate_token, interview, test_db) # Pass test_db

    # 2. Find the response ID for the first question using test_db
    responses_collection = test_db[settings.MONGODB_COLLECTION_RESPONSES] # Use test_db
    response_doc = await responses_collection.find_one({"interview_id": interview_id, "question_id": q1_id, "candidate_id": candidate_object_id})
    assert response_doc is not None, f"Response doc for QID {q1_id} not found"
    response_id = str(response_doc["_id"])

    # 3. Rely on default mock return from conftest: {"score": 3.5, "feedback": "[AI]: Mock evaluation."}
    ai_score = 3.5
    ai_feedback = "[AI]: Mock evaluation."

    # 4. Trigger AI evaluation via API
    response = client.post(f"/api/v1/interview/responses/{response_id}/evaluate", headers={"Authorization": f"Bearer {hr_token}"})
    assert response.status_code == status.HTTP_200_OK
    updated_response_data = response.json()

    # 5. Assert response from API and DB state
    assert updated_response_data["response_id"] == response_id
    assert updated_response_data["score"] == pytest.approx(ai_score)
    assert updated_response_data["feedback"] == ai_feedback
    assert updated_response_data["evaluated_by"] is not None

    final_response_doc = await responses_collection.find_one({"_id": ObjectId(response_id)}) # Use test_db implicitly
    assert final_response_doc is not None
    assert final_response_doc["score"] == pytest.approx(ai_score)
    assert final_response_doc["feedback"] == ai_feedback

@pytest.mark.asyncio
async def test_gemini_fallback_questions(client, hr_token, candidate_user, test_db, mock_gemini): # Added test_db, Request mock_gemini
    # --- Corrected: Set return_value directly on the mock ---
    mock_gemini.return_value = [] # Simulate Gemini failing to generate questions
    # --- End Correction ---

    # Ensure default questions exist (or skip test if they don't)
    if await test_db[settings.MONGODB_COLLECTION_QUESTIONS].count_documents({}) == 0: # Use test_db
        pytest.skip("Skipping fallback test: Default questions not seeded/accessible in test DB.")

    interview_data = {
        "candidate_id": candidate_user["id"],
        "scheduled_time": (datetime.utcnow() + timedelta(days=1)).isoformat()+"Z",
        "role": "SE",
        "tech_stack": ["Py"]
    }
    response = client.post("/api/v1/interview/schedule", json=interview_data, headers={"Authorization": f"Bearer {hr_token}"})

    assert response.status_code == status.HTTP_201_CREATED
    interview = response.json()
    assert len(interview["questions"]) > 0
    assert ObjectId.is_valid(interview["questions"][0].get("question_id"))
    # --- Corrected: Assert call on the mock directly ---
    mock_gemini.assert_awaited_once()
    # --- End Correction ---

@pytest.mark.asyncio
async def test_unauthorized_role_access(client, hr_token, candidate_token, admin_token):
    # Candidate trying to access HR/Admin route
    response = client.get("/api/v1/interview/all", headers={"Authorization": f"Bearer {candidate_token}"})
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # HR trying to access Admin route
    response = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {hr_token}"})
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Admin accessing HR/Admin route (should succeed)
    response = client.get("/api/v1/interview/all", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == status.HTTP_200_OK

    # Admin accessing Admin route (should succeed)
    response = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == status.HTTP_200_OK