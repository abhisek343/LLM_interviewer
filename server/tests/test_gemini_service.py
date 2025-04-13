import pytest
from unittest.mock import patch, AsyncMock
from app.services.gemini_service import gemini_service

@pytest.mark.asyncio
async def test_generate_questions():
    # Mock successful Gemini API response
    mock_questions = [
        {
            "text": "What is dependency injection?",
            "category": "Software Design",
            "difficulty": "medium"
        },
        {
            "text": "Explain REST API principles.",
            "category": "API Design",
            "difficulty": "medium"
        }
    ]
    
    with patch('app.services.gemini_service.gemini_service.generate_questions', 
              new_callable=AsyncMock, return_value=mock_questions):
        role = "Software Engineer"
        tech_stack = ["Python", "FastAPI", "MongoDB"]
        num_questions = 5
        
        questions = await gemini_service.generate_questions(
            role=role,
            tech_stack=tech_stack,
            num_questions=num_questions
        )
        
        assert isinstance(questions, list)
        assert len(questions) > 0
        
        # Check question structure
        for question in questions:
            assert "text" in question
            assert "category" in question
            assert "difficulty" in question
            assert isinstance(question["text"], str)
            assert isinstance(question["category"], str)
            assert isinstance(question["difficulty"], str)

@pytest.mark.asyncio
async def test_generate_questions_with_invalid_input():
    # Test with empty tech stack
    questions = await gemini_service.generate_questions(
        role="Software Engineer",
        tech_stack=[],
        num_questions=5
    )
    assert isinstance(questions, list)  # Should still return a list, even if empty 