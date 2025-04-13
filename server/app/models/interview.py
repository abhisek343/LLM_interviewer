from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Question(BaseModel):
    question_id: str
    text: str
    category: str
    difficulty: str
    created_at: datetime = datetime.utcnow()

class Interview(BaseModel):
    interview_id: str
    candidate_id: str
    hr_id: str
    scheduled_time: datetime
    status: str = "scheduled"  # scheduled, in_progress, completed
    questions: List[Question] = []
    created_at: datetime = datetime.utcnow()

class InterviewResponse(BaseModel):
    response_id: str
    interview_id: str
    candidate_id: str
    question_id: str
    answer: str
    score: Optional[float] = None
    feedback: Optional[str] = None
    submitted_at: datetime = datetime.utcnow()

class InterviewResult(BaseModel):
    result_id: str
    interview_id: str
    candidate_id: str
    total_score: float
    feedback: str
    completed_at: datetime = datetime.utcnow() 