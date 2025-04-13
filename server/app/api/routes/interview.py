from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.schemas.interview import (
    QuestionOut, InterviewCreate, InterviewOut,
    InterviewResponseCreate, InterviewResponseOut,
    InterviewResultOut
)
from app.api.routes.auth import get_current_user
from app.schemas.user import UserOut
from app.db.mongodb import mongodb
from app.services.gemini_service import gemini_service
from uuid import uuid4
from datetime import datetime

router = APIRouter(prefix="/interview", tags=["interview"])

@router.get("/default-questions", response_model=List[QuestionOut])
async def get_default_questions():
    questions = await mongodb.db.questions.find().to_list(length=10)
    return [QuestionOut(**q) for q in questions]

@router.post("/schedule", response_model=InterviewOut)
async def schedule_interview(
    interview: InterviewCreate,
    current_user: UserOut = Depends(get_current_user)
):
    if current_user.role != "hr":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR can schedule interviews"
        )
    
    # Generate questions using Gemini
    generated_questions = await gemini_service.generate_questions(
        role=interview.role,
        tech_stack=interview.tech_stack,
        num_questions=5
    )
    
    # If Gemini fails, use default questions
    if not generated_questions:
        default_questions = await mongodb.db.questions.find().to_list(length=5)
        questions = [QuestionOut(**q) for q in default_questions]
    else:
        questions = [
            QuestionOut(
                question_id=str(uuid4()),
                text=q["text"],
                category=q["category"],
                difficulty=q["difficulty"],
                created_at=datetime.utcnow()
            ) for q in generated_questions
        ]
    
    interview_dict = interview.model_dump()
    interview_dict["interview_id"] = str(uuid4())
    interview_dict["hr_id"] = current_user.email
    interview_dict["status"] = "scheduled"
    interview_dict["questions"] = [q.model_dump() for q in questions]
    
    result = await mongodb.db.interviews.insert_one(interview_dict)
    interview_dict["_id"] = str(result.inserted_id)
    
    return InterviewOut(**interview_dict)

@router.post("/submit-response", response_model=InterviewResponseOut)
async def submit_response(
    response: InterviewResponseCreate,
    current_user: UserOut = Depends(get_current_user)
):
    if current_user.role != "candidate":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can submit responses"
        )
    
    # Verify interview exists and is assigned to candidate
    interview = await mongodb.db.interviews.find_one({
        "interview_id": response.interview_id,
        "candidate_id": current_user.email
    })
    
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found or not assigned to candidate"
        )
    
    response_dict = response.model_dump()
    response_dict["response_id"] = str(uuid4())
    response_dict["candidate_id"] = current_user.email
    
    result = await mongodb.db.responses.insert_one(response_dict)
    response_dict["_id"] = str(result.inserted_id)
    
    # Update interview status
    await mongodb.db.interviews.update_one(
        {"_id": response.interview_id},
        {"$set": {"status": "completed"}}
    )
    
    return InterviewResponseOut(**response_dict)

@router.get("/results/{user_id}", response_model=InterviewResultOut)
async def get_interview_results(
    user_id: str,
    current_user: UserOut = Depends(get_current_user)
):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR and Admin can view results"
        )
    
    # Get all responses for the user
    responses = await mongodb.db.responses.find({
        "candidate_id": user_id
    }).to_list(length=None)
    
    if not responses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No results found for this user"
        )
    
    # Calculate total score (simple average for now)
    total_score = sum(r.get("score", 0) for r in responses) / len(responses)
    
    result = {
        "result_id": str(uuid4()),
        "interview_id": responses[0]["interview_id"],
        "candidate_id": user_id,
        "total_score": total_score,
        "feedback": "Overall performance feedback",  # In real app, generate this
        "completed_at": datetime.utcnow()
    }
    
    return InterviewResultOut(**result) 