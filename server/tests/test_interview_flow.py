import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_password_hash, create_access_token
from app.db.mongodb import mongodb
from datetime import datetime, timedelta

client = TestClient(app)

@pytest.fixture(autouse=True)
async def clear_db():
    # Clear all collections before each test
    await mongodb.client.llminterview.users.delete_many({})
    await mongodb.client.llminterview.interviews.delete_many({})
    await mongodb.client.llminterview.responses.delete_many({})
    yield

@pytest.fixture
def hr_token():
    # Create a test HR user
    user = {
        "email": "hr@example.com",
        "role": "hr",
        "hashed_password": get_password_hash("testpassword123")
    }
    return create_access_token(data={"sub": user["email"], "role": user["role"]})

@pytest.fixture
def candidate_token():
    # Create a test candidate user
    user = {
        "email": "candidate@example.com",
        "role": "candidate",
        "hashed_password": get_password_hash("testpassword123")
    }
    return create_access_token(data={"sub": user["email"], "role": user["role"]})

@pytest.fixture
def admin_token():
    # Create a test admin user
    user = {
        "email": "admin@example.com",
        "role": "admin",
        "hashed_password": get_password_hash("testpassword123")
    }
    return create_access_token(data={"sub": user["email"], "role": user["role"]})

@pytest.mark.asyncio
async def test_full_interview_flow(hr_token, candidate_token):
    # 1. HR schedules interview
    interview_data = {
        "candidate_id": "candidate@example.com",
        "scheduled_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "role": "Software Engineer",
        "tech_stack": ["Python", "FastAPI"]
    }
    
    response = client.post(
        "/interview/schedule",
        json=interview_data,
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == 200
    interview = response.json()
    interview_id = interview["interview_id"]
    
    # 2. Candidate submits response
    response_data = {
        "interview_id": interview_id,
        "answers": [
            {
                "question_id": interview["questions"][0]["question_id"],
                "answer_text": "Test answer"
            }
        ]
    }
    
    response = client.post(
        "/interview/submit-response",
        json=response_data,
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    assert response.status_code == 200
    
    # 3. HR views results
    response = client.get(
        f"/interview/results/candidate@example.com",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == 200
    results = response.json()
    assert results["candidate_id"] == "candidate@example.com"
    assert "total_score" in results
    assert "feedback" in results

@pytest.mark.asyncio
async def test_candidate_cannot_regenerate_questions(hr_token, candidate_token):
    # First create an interview
    interview_data = {
        "candidate_id": "candidate@example.com",
        "scheduled_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "role": "Software Engineer",
        "tech_stack": ["Python", "FastAPI"]
    }
    
    response = client.post(
        "/interview/schedule",
        json=interview_data,
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == 200
    interview = response.json()
    
    # Try to regenerate questions as candidate
    response = client.post(
        f"/interview/generate-questions/{interview['interview_id']}",
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    assert response.status_code == 409
    assert "Questions already generated" in response.json()["detail"]

@pytest.mark.asyncio
async def test_gemini_fallback_questions(hr_token):
    # Mock Gemini service to return None
    with patch('app.services.gemini_service.gemini_service.generate_questions', 
              new_callable=AsyncMock, return_value=None):
        interview_data = {
            "candidate_id": "candidate@example.com",
            "scheduled_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "role": "Software Engineer",
            "tech_stack": ["Python", "FastAPI"]
        }
        
        response = client.post(
            "/interview/schedule",
            json=interview_data,
            headers={"Authorization": f"Bearer {hr_token}"}
        )
        assert response.status_code == 200
        interview = response.json()
        
        # Verify fallback questions were used
        assert len(interview["questions"]) > 0
        assert all(q["category"] in ["Programming Concepts", "API Design", "Database", "Software Design", "Testing"] 
                  for q in interview["questions"])

@pytest.mark.asyncio
async def test_unauthorized_role_access(hr_token, candidate_token, admin_token):
    # Test candidate trying to access HR route
    response = client.get(
        "/interview/results/candidate@example.com",
        headers={"Authorization": f"Bearer {candidate_token}"}
    )
    assert response.status_code == 403
    
    # Test HR trying to access admin route
    response = client.get(
        "/admin/dashboard",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == 403
    
    # Test admin accessing HR route (should work)
    response = client.get(
        "/interview/results/candidate@example.com",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_gemini_question_generation(hr_token):
    # Mock Gemini service to return custom questions
    mock_questions = [
        {"question_text": "What is dependency injection?", "category": "Software Design"},
        {"question_text": "Explain REST API best practices", "category": "API Design"},
        {"question_text": "How do you handle database transactions?", "category": "Database"},
        {"question_text": "Describe test-driven development", "category": "Testing"},
        {"question_text": "What are Python decorators?", "category": "Programming Concepts"}
    ]
    
    with patch('app.services.gemini_service.gemini_service.generate_questions', 
              new_callable=AsyncMock, return_value=mock_questions):
        interview_data = {
            "candidate_id": "candidate@example.com",
            "scheduled_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "role": "Software Engineer",
            "tech_stack": ["Python", "FastAPI"]
        }
        
        response = client.post(
            "/interview/schedule",
            json=interview_data,
            headers={"Authorization": f"Bearer {hr_token}"}
        )
        assert response.status_code == 200
        interview = response.json()
        
        # Verify Gemini-generated questions were used
        assert len(interview["questions"]) == len(mock_questions)
        for i, q in enumerate(interview["questions"]):
            assert q["question_text"] == mock_questions[i]["question_text"]
            assert q["category"] == mock_questions[i]["category"] 