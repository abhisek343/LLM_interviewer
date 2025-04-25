# LLM_interviewer/server/tests/test_gemini_service.py

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import json
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import os

from app.services.gemini_service import GeminiService, gemini_service # Import instance too
from app.core.config import settings
# --- Corrected Import ---
from app.schemas.interview import QuestionOut # Import QuestionOut schema
# --- End Correction ---

# Mock the configure call if API key is needed during import/setup
# If GeminiService checks API key on init, mock settings or the configure call itself
# Example: patch('app.services.gemini_service.genai.configure') if needed

# Fixtures provided by conftest.py: mock_gemini (autouse=True)

# --- Tests for _clean_json_response ---

@pytest.mark.asyncio
async def test_clean_json_response():
    """Test the JSON cleaning functionality."""
    # Test with valid JSON
    valid_json = '{"key": "value"}'
    assert gemini_service._clean_json_response(valid_json) == '{"key": "value"}'
    
    # Test with extra text before JSON
    with_text = 'Some text {"key": "value"}'
    assert gemini_service._clean_json_response(with_text) == '{"key": "value"}'
    
    # Test with multiple JSON objects
    multiple = '{"key1": "value1"}{"key2": "value2"}'
    assert gemini_service._clean_json_response(multiple) == '{"key1": "value1"}'

# --- Tests for generate_questions ---

@pytest.mark.asyncio
async def test_generate_questions_success(mock_gemini):
    """Test successful question generation."""
    questions = await gemini_service.generate_questions("Python", ["Senior"])
    assert len(questions) == 2
    assert all(q["text"] for q in questions)
    assert all(q["category"] for q in questions)
    assert all(q["difficulty"] for q in questions)
    assert all(q["question_id"] for q in questions)
    assert all(q["created_at"] for q in questions)

@pytest.mark.asyncio
async def test_generate_questions_with_resume(mock_gemini):
    """Test question generation with resume context."""
    resume_text = "Experienced Python developer with skills in FastAPI."
    questions = await gemini_service.generate_questions("Python", ["Senior"], resume_text)
    assert len(questions) == 2
    # Verify the prompt included the resume context
    mock_gemini.assert_called_once()
    prompt_arg = mock_gemini.call_args[0][0]
    assert "resume" in prompt_arg.lower()
    assert resume_text in prompt_arg

@pytest.mark.asyncio
async def test_generate_questions_api_error():
    """Test handling of API errors during question generation."""
    with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
              new_callable=AsyncMock) as mock_api:
        mock_api.side_effect = Exception("API Error")
        questions = await gemini_service.generate_questions("Python", ["Senior"])
        assert questions == []

@pytest.mark.asyncio
async def test_generate_questions_invalid_json():
    """Test handling of invalid JSON responses."""
    with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
              new_callable=AsyncMock) as mock_api:
        mock_response = MagicMock()
        mock_response.text = "Invalid JSON"
        mock_api.return_value = mock_response
        questions = await gemini_service.generate_questions("Python", ["Senior"])
        assert questions == []

@pytest.mark.asyncio
async def test_generate_questions_non_list_json():
    """Test handling of non-list JSON responses."""
    with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
              new_callable=AsyncMock) as mock_api:
        mock_response = MagicMock()
        mock_response.text = '{"not_a_list": true}'
        mock_api.return_value = mock_response
        questions = await gemini_service.generate_questions("Python", ["Senior"])
        assert questions == []

@pytest.mark.asyncio
async def test_generate_questions_empty_list_json():
    """Test handling of empty list JSON responses."""
    with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
              new_callable=AsyncMock) as mock_api:
        mock_response = MagicMock()
        mock_response.text = '[]'
        mock_api.return_value = mock_response
        questions = await gemini_service.generate_questions("Python", ["Senior"])
        assert questions == []

# --- Tests for evaluate_answer ---

@pytest.mark.asyncio
async def test_evaluate_answer_success(mock_gemini):
    """Test successful answer evaluation."""
    evaluation = await gemini_service.evaluate_answer("Question", "Answer")
    assert evaluation is not None
    assert "score" in evaluation
    assert "feedback" in evaluation
    assert isinstance(evaluation["score"], float)
    assert isinstance(evaluation["feedback"], str)

@pytest.mark.asyncio
async def test_evaluate_answer_api_error():
    """Test handling of API errors during answer evaluation."""
    with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
              new_callable=AsyncMock) as mock_api:
        mock_api.side_effect = Exception("API Error")
        evaluation = await gemini_service.evaluate_answer("Question", "Answer")
        assert evaluation is None

@pytest.mark.asyncio
async def test_evaluate_answer_invalid_json():
    """Test handling of invalid JSON responses."""
    with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
              new_callable=AsyncMock) as mock_api:
        mock_response = MagicMock()
        mock_response.text = "Invalid JSON"
        mock_api.return_value = mock_response
        evaluation = await gemini_service.evaluate_answer("Question", "Answer")
        assert evaluation is None

@pytest.mark.asyncio
async def test_evaluate_answer_invalid_score_type():
    """Test handling of invalid score types."""
    with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
              new_callable=AsyncMock) as mock_api:
        mock_response = MagicMock()
        mock_response.text = '{"score": "not_a_number", "feedback": "test"}'
        mock_api.return_value = mock_response
        evaluation = await gemini_service.evaluate_answer("Question", "Answer")
        assert evaluation is None

@pytest.mark.asyncio
async def test_evaluate_answer_score_out_of_range():
    """Test handling of scores outside valid range."""
    with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
              new_callable=AsyncMock) as mock_api:
        # Test score too low
        mock_response_low = MagicMock()
        mock_response_low.text = '{"score": -1, "feedback": "test"}'
        mock_api.return_value = mock_response_low
        evaluation_low = await gemini_service.evaluate_answer("Question", "Answer")
        assert evaluation_low is None

        # Test score too high
        mock_response_high = MagicMock()
        mock_response_high.text = '{"score": 6, "feedback": "test"}'
        mock_api.return_value = mock_response_high
        evaluation_high = await gemini_service.evaluate_answer("Question", "Answer")
        assert evaluation_high is None

@pytest.mark.asyncio
async def test_evaluate_answer_missing_keys():
    """Test handling of responses missing required keys."""
    with patch('app.services.gemini_service.gemini_service.model.generate_content_async', 
              new_callable=AsyncMock) as mock_api:
        # Test missing score
        mock_response_no_score = MagicMock()
        mock_response_no_score.text = '{"feedback": "test"}'
        mock_api.return_value = mock_response_no_score
        evaluation_no_score = await gemini_service.evaluate_answer("Question", "Answer")
        assert evaluation_no_score is None

        # Test missing feedback
        mock_response_no_feedback = MagicMock()
        mock_response_no_feedback.text = '{"score": 3.5}'
        mock_api.return_value = mock_response_no_feedback
        evaluation_no_feedback = await gemini_service.evaluate_answer("Question", "Answer")
        assert evaluation_no_feedback is None

@pytest.mark.asyncio
async def test_evaluate_answer_missing_input():
    """Test handling of missing input."""
    with pytest.raises(ValueError, match="Question and answer text cannot be empty"):
        await gemini_service.evaluate_answer("", "Answer")
    
    with pytest.raises(ValueError, match="Question and answer text cannot be empty"):
        await gemini_service.evaluate_answer("Question", "")

# --- Test Initialization ---

@patch.dict(settings.model_dump(), {"GOOGLE_API_KEY": ""})
@patch('app.services.gemini_service.genai.configure')
def test_service_initialization_no_api_key(mock_configure):
    """Test service initialization logs warning and sets model=None if no API key."""
    with pytest.warns(UserWarning, match="GOOGLE_API_KEY not found"):
        service_no_key = GeminiService()
    assert service_no_key.model is None
    mock_configure.assert_not_called()

@pytest.mark.asyncio
async def test_service_initialization_no_api_key(caplog):
    """Test service initialization without API key."""
    original_key = os.environ.get("GOOGLE_API_KEY")
    os.environ.pop("GOOGLE_API_KEY", None)
    
    try:
        with patch('app.services.gemini_service.genai.configure') as mock_configure:
            service = gemini_service.__class__()
            assert service.model is None
            mock_configure.assert_not_called()
            assert "GOOGLE_API_KEY not found" in caplog.text
    finally:
        if original_key:
            os.environ["GOOGLE_API_KEY"] = original_key

# Note: A test for successful initialization is implicitly covered by other tests
# assuming the API key is correctly set in the environment for the main test suite run.
