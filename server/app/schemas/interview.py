from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import uuid4

class QuestionBase(BaseModel):
    text: str
    category: str
    difficulty: str

class QuestionCreate(QuestionBase):
    pass

class QuestionOut(QuestionBase):
    question_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class InterviewBase(BaseModel):
    candidate_id: str
    scheduled_time: datetime

class InterviewCreate(InterviewBase):
    pass

class InterviewOut(InterviewBase):
    interview_id: str
    hr_id: str
    status: str
    questions: List[QuestionOut]
    created_at: datetime

    class Config:
        from_attributes = True

class InterviewResponseBase(BaseModel):
    interview_id: str
    question_id: str
    answer: str

class InterviewResponseCreate(InterviewResponseBase):
    pass

class InterviewResponseOut(InterviewResponseBase):
    response_id: str
    candidate_id: str
    score: Optional[float]
    feedback: Optional[str]
    submitted_at: datetime

    class Config:
        from_attributes = True

class InterviewResultOut(BaseModel):
    result_id: str
    interview_id: str
    candidate_id: str
    total_score: float
    feedback: str
    completed_at: datetime

    class Config:
        from_attributes = True 