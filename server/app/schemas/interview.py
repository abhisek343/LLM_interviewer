# LLM_interviewer/server/app/schemas/interview.py

from pydantic import BaseModel, Field, field_validator, ConfigDict # Import v2 components
from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import uuid # Added import for uuid (needed for default factory if used)

# Import the custom ObjectId type handler from user schemas
# Ensure this path is correct relative to your project structure
from .user import PyObjectIdStr # Still needed for other models in this file like Interview, InterviewResponse
from app.core.schema_utils import clean_model_title # Import the decorator

# --- Base Question Schema ---
class QuestionBase(BaseModel):
    text: str = Field(..., description="The text of the interview question")
    category: str = Field(..., description="Category of the question (e.g., Behavioral, Technical)")
    difficulty: str = Field(..., description="Difficulty level (e.g., Easy, Medium, Hard)")
    # Added question_id here as it's used in the embedded doc and mock data
    question_id: Optional[str] = Field(None, description="Custom identifier for the question")

# Schema for creating a question (inherits from Base)
# This might be used if questions were managed in a separate collection
class QuestionCreate(QuestionBase):
    pass

# Schema for Question output FROM THE QUESTIONS COLLECTION (includes DB _id)
class Question(QuestionBase):
    id: PyObjectIdStr = Field(..., alias="_id")
    # question_id: Optional[str] = Field(None, description="Optional custom identifier for the question") # Already in Base
    created_at: datetime

    # Use v2 model_config
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

# Output schema for individual questions (if fetched directly)
class QuestionOut(Question): # Often Question itself is sufficient for output
    pass

# --- Base Interview Schema ---
class InterviewBase(BaseModel):
    candidate_id: PyObjectIdStr = Field(..., description="ID of the candidate")
    hr_id: PyObjectIdStr = Field(..., description="ID of the HR personnel who scheduled")
    job_title: str = Field(..., description="Job title for the interview")
    job_description: Optional[str] = Field(None, description="Job description")
    scheduled_time: Optional[datetime] = Field(None, description="Time the interview is scheduled for")
    status: str = Field("Scheduled", description="Status (e.g., Scheduled, In Progress, Completed, Evaluated)")

# Schema for creating an interview (Payload for POST /interview/schedule)
@clean_model_title
class InterviewCreate(BaseModel):
    candidate_id: PyObjectIdStr 
    # hr_id: PyObjectIdStr # REMOVED - Determined server-side from token
    job_title: str
    job_description: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    role: str = Field(..., description="Role being interviewed for (e.g., Software Engineer)")
    tech_stack: List[str] = Field(default_factory=list, description="Relevant technical skills/stack")

    class Config:
        # title = "InterviewCreate" # Title is now set by @clean_model_title decorator
        json_schema_extra = {
            "example": {
                "candidate_id": "60d5ec49f72f3b5e9f1d0a1c",
                "job_title": "Senior Python Developer",
                "job_description": "Develop and maintain web applications.",
                "role": "Software Engineer",
                "tech_stack": ["python", "fastapi", "mongodb"]
            }
        }
        # populate_by_name = True # If these were needed, ensure decorator or manual add
        # arbitrary_types_allowed = True

# Schema representing the Interview document IN THE DATABASE
class Interview(InterviewBase):
    id: PyObjectIdStr = Field(..., alias="_id")
    interview_id: str = Field(..., description="Custom unique ID for the interview session") # Added this
    # Embed the generated questions directly
    questions: List[Dict[str, Any]] = Field(default_factory=list, description="List of generated questions embedded")
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Results fields can be added here too if storing directly on the interview doc
    overall_score: Optional[float] = Field(None, description="Overall score if calculated")
    overall_feedback: Optional[str] = Field(None, description="Overall feedback if provided")
    completed_at: Optional[datetime] = None # Added for completion time
    evaluated_by: Optional[str] = None # Added tracking
    evaluated_at: Optional[datetime] = None # Added tracking


    # Use v2 model_config
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str} # Ensure ObjectId is serialized correctly
    )

# Schema for Interview Output (API Response for GET /interview/{id})
class InterviewOut(InterviewBase): # Inherit from Base, add fields needed for output
    id: PyObjectIdStr = Field(..., alias="_id") # MongoDB ObjectId
    interview_id: Optional[str] = Field(None, description="Custom interview identifier generated during creation")
    # Return the embedded questions using QuestionBase which doesn't require _id
    questions: Optional[List[QuestionBase]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None # Include completion time
    overall_score: Optional[float] = None # Include results if available
    overall_feedback: Optional[str] = None
    evaluated_by: Optional[str] = None # Include evaluator info
    evaluated_at: Optional[datetime] = None # Include evaluation time

    # Use v2 config style for consistency
    model_config = ConfigDict(
        from_attributes = True, # Renamed from orm_mode
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None} # Handle datetime too
    )


# --- Interview Response Schemas ---

# === NEW Schema for submitting a SINGLE response ===
class SingleResponseSubmit(BaseModel):
    """Schema for the request body when submitting a single answer."""
    interview_id: str = Field(..., description="The custom ID of the interview session")
    question_id: str = Field(..., description="The ID of the question being answered")
    answer: str = Field(..., min_length=1, description="The candidate's answer text") # Use 'answer' to match endpoint logic

    model_config = ConfigDict(
         json_schema_extra={
             "example": {
                 "interview_id": "some_interview_uuid",
                 "question_id": "some_question_uuid",
                 "answer": "My detailed answer to this specific question."
            }
        }
    )
# === END NEW Schema ===

# Schema for the structure of submitted answers in SubmitAnswersRequest (for /submit-all)
class AnswerItem(BaseModel):
    question_id: str
    answer_text: str # Keep as answer_text for consistency with /submit-all endpoint

    model_config = ConfigDict(
         json_schema_extra={
             "example": {"question_id": "q1_uuid", "answer_text": "My answer..."}
        }
    )

# Request body for submitting all answers (/submit-all)
class SubmitAnswersRequest(BaseModel):
    interview_id: str # Use custom interview_id
    answers: List[AnswerItem] # Use the specific AnswerItem schema


# Base for response data stored in DB (used by InterviewResponse)
class InterviewResponseBase(BaseModel):
    interview_id: str
    question_id: str
    candidate_id: PyObjectIdStr
    answer: str # Renamed from answer_text for consistency with DB field in route
    submitted_at: datetime

# Schema representing the Response document IN THE DATABASE
class InterviewResponse(InterviewResponseBase):
    id: PyObjectIdStr = Field(..., alias="_id")
    score: Optional[float] = Field(None, description="Score assigned by LLM or HR")
    feedback: Optional[str] = Field(None, description="Feedback provided during evaluation")
    evaluated_by: Optional[str] = None # Added tracking
    evaluated_at: Optional[datetime] = None # Added tracking

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None}
    )

# Schema for Response Output (API Response for GET /responses and POST /submit-response)
class InterviewResponseOut(InterviewResponse):
    # Inherits all fields including 'id' aliased from '_id'
    pass


# --- Schemas for Specific API Endpoints ---

# Schema for individual feedback item within InterviewResultSubmit
class ResponseFeedbackItem(BaseModel):
    question_id: str
    score: Optional[float] = Field(None, ge=0, le=5)
    feedback: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"question_id": "q1_uuid", "score": 4.0, "feedback": "Good answer."}
        }
    )

# Schema for submitting evaluation results (POST /{interview_id}/results)
class InterviewResultSubmit(BaseModel):
    # interview_id: str # REMOVED - comes from path parameter
    overall_score: Optional[float] = Field(None, ge=0, le=5) # Optional overall score
    overall_feedback: Optional[str] = None
    responses_feedback: Optional[List[ResponseFeedbackItem]] = Field(None, description="Optional list of feedback per response")
    status: Optional[str] = Field(None, description="e.g., Evaluated") # Optional status update

    model_config = ConfigDict(
         json_schema_extra={
             "example": {
                 "responses_feedback": [{"question_id": "q1_id", "score": 4.0, "feedback": "Good"}],
                 "overall_score": 4.0,
                 "overall_feedback": "Overall good."
             }
        }
    )


# Schema for returning interview results summary (used by GET /results/{id})
class InterviewResultOut(BaseModel):
    result_id: str # e.g., "result_INTERVIEW_ID"
    interview_id: str
    candidate_id: PyObjectIdStr
    total_score: Optional[float] = None # Final score (manual or calculated)
    overall_feedback: Optional[str] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True, # Allow mapping from DB fields if needed
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None}
    )
