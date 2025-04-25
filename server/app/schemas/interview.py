# LLM_interviewer/server/app/schemas/interview.py

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, constr # Added constr
# from uuid import uuid4 # Not used here
from app.core.config import settings # Import settings for validation values

class QuestionBase(BaseModel):
    text: str
    # Make category/difficulty optional as they might not always come from Gemini/Defaults
    category: Optional[str] = None
    difficulty: Optional[str] = None

class QuestionCreate(QuestionBase):
    pass

class QuestionOut(QuestionBase):
    question_id: str # Should be populated when creating/retrieving
    created_at: Optional[datetime] = None # Make optional

    class Config:
        from_attributes = True # Use from_attributes for Pydantic v2

class InterviewBase(BaseModel):
    candidate_id: str # Candidate's DB ID (_id as string)
    scheduled_time: datetime
    role: str # Added in previous steps
    tech_stack: List[str] # Added in previous steps

class InterviewCreate(InterviewBase):
     # Inherits fields from InterviewBase
     class Config:
        json_schema_extra = {
            "example": {
                "candidate_id": "60d5ecf1b3f8f5a9f3e8e1c1",
                "scheduled_time": "2024-08-15T14:30:00Z",
                "role": "Backend Developer",
                "tech_stack": ["Python", "FastAPI", "Docker", "MongoDB"]
            }
        }

class InterviewOut(InterviewBase):
    # Use DB _id as the primary ID for the interview document
    id: str = Field(alias="_id")
    interview_id: str # Keep separate generated ID if used for sharing/URLs
    hr_id: str # HR user's DB ID (_id as string)
    status: str
    questions: List[QuestionOut]
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Overall results stored on the interview document
    overall_score: Optional[float] = None
    overall_feedback: Optional[str] = None
    evaluated_by: Optional[str] = None # Username of evaluator
    evaluated_at: Optional[datetime] = None # Timestamp of evaluation

    class Config:
        from_attributes = True
        populate_by_name = True # Allow population by field name or alias (_id)

class InterviewResponseBase(BaseModel):
    interview_id: str
    question_id: str
    answer: str

class InterviewResponseCreate(InterviewResponseBase):
    pass

class InterviewResponseOut(InterviewResponseBase):
    # Use response's own DB ID
    response_id: str = Field(alias="_id")
    candidate_id: str # Candidate's DB ID
    # Score/Feedback for this specific response
    score: Optional[float] = None
    feedback: Optional[str] = None
    submitted_at: datetime
    # Track evaluation specific to this response (e.g., by AI trigger)
    evaluated_by: Optional[str] = None
    evaluated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True # Allow population by field name or alias (_id)

# --- NEW Schema for submitting score/feedback PER RESPONSE ---
class ResponseFeedbackCreate(BaseModel):
    question_id: str = Field(..., description="The ID of the question being evaluated")
    # Use settings for score validation range
    score: Optional[float] = Field(
        None,
        ge=settings.EVALUATION_SCORE_MIN, # Use setting
        le=settings.EVALUATION_SCORE_MAX, # Use setting
        description=f"Score for this answer ({settings.EVALUATION_SCORE_MIN}-{settings.EVALUATION_SCORE_MAX} scale)"
    )
    feedback: Optional[constr(strip_whitespace=True, max_length=1000)] = Field( # Add length limit
        None,
        description="Feedback specific to this answer (max 1000 chars)"
    )

    class Config:
         json_schema_extra = {
            "example": {
                "question_id": "q_uuid_or_db_id_1",
                "score": 4.0,
                "feedback": "Good explanation, could provide more specific examples."
            }
        }
# --- End NEW Schema ---

class SubmitAnswersRequest(BaseModel):
    """Schema for submitting all answers for an interview at once."""
    interview_id: str
    responses: List[InterviewResponseCreate] # Uses the existing schema for individual responses

    class Config:
        json_schema_extra = {
            "example": {
                "interview_id": "some_interview_uuid_or_db_id",
                "responses": [
                    {"question_id": "q_id_1", "answer": "My answer to question 1."},
                    {"question_id": "q_id_2", "answer": "My answer to question 2."}
                ]
            }
        }
# --- RENAMED/MODIFIED Schema for Submitting All Results/Feedback ---
class InterviewResultSubmit(BaseModel):
    # Payload for POST /interview/{id}/results endpoint

    # List of feedback items for individual responses (Optional)
    responses_feedback: Optional[List[ResponseFeedbackCreate]] = Field(
        None,
        description="Feedback and scores for individual responses"
    )

    # Overall assessment (Optional)
    # Use settings for score validation range
    overall_score: Optional[float] = Field(
        None,
        ge=settings.EVALUATION_SCORE_MIN, # Use setting
        le=settings.EVALUATION_SCORE_MAX, # Use setting
        description=f"Overall score ({settings.EVALUATION_SCORE_MIN}-{settings.EVALUATION_SCORE_MAX} scale, optional override)"
    )
    overall_feedback: Optional[constr(strip_whitespace=True, max_length=5000)] = Field( # Add length limit
        None,
        description="Overall feedback summary (max 5000 chars, optional)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "responses_feedback": [
                    {"question_id": "q_id_1", "score": 4.5, "feedback": "Very clear."},
                    {"question_id": "q_id_2", "score": 3.0, "feedback": "Confusing."},
                    {"question_id": "q_id_3", "score": None, "feedback": "Skipped."} # Example without score
                ],
                "overall_score": 3.8, # Can be calculated or manually entered
                "overall_feedback": "Overall good technical understanding, communication needs work."
            }
        }
# --- End RENAMED/MODIFIED Schema ---


# Existing InterviewResultOut - Represents data returned by GET /results/{id}
# May need adjustment based on how results are calculated/stored.
class InterviewResultOut(BaseModel):
    result_id: str # Usually f"result_{interview_id}"
    interview_id: str
    candidate_id: str
    total_score: Optional[float] = None # Make optional as it might be pending
    overall_feedback: Optional[str] = None # Get from Interview doc
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True