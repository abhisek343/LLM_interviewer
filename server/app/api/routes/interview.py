# LLM_interviewer/server/app/api/routes/interview.py

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from app.schemas.interview import (
    QuestionOut, InterviewCreate, InterviewOut,
    SingleResponseSubmit,
    InterviewResponseOut,
    InterviewResultOut, SubmitAnswersRequest, AnswerItem,
    InterviewResultSubmit, ResponseFeedbackItem
)
from app.core.security import get_current_active_user
# Import User model to check roles, statuses, and assigned IDs
from app.models.user import User, CandidateMappingStatus, HrStatus # Import User and status literals
# Import UserOut for dependency type hint where appropriate
from app.schemas.user import UserOut, PyObjectIdStr # Import PyObjectIdStr for validation if needed
from app.db.mongodb import mongodb
from app.core.config import settings
from app.services.gemini_service import gemini_service, GeminiServiceError
from uuid import uuid4
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio # Import asyncio for placeholder sleeps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["Interview"])

# --- Helper function to Get ObjectId ---
def get_object_id(id_str: str) -> ObjectId:
    try:
        # Ensure input is a string before passing to ObjectId
        return ObjectId(str(id_str))
    except (InvalidId, TypeError) as e:
        logger.error(f"Invalid ObjectId format: '{id_str}'. Error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ID format: {id_str}")

# --- Helper Dependencies for Role Checks ---
# Combined HR/Admin check for routes accessible by both
async def require_hr_or_admin(current_user_dep: User = Depends(get_current_active_user)):
    """Dependency ensuring user is HR or Admin. Fetches full User doc."""
    if current_user_dep.role not in ["hr", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted. HR or Admin privileges required.")
    # Fetch full doc for potential checks within routes
    db = mongodb.get_db()
    user_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": get_object_id(current_user_dep.id)})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Authenticated user not found in database.")
    
    logger.debug(f"require_hr_or_admin: Fetched user_doc for {current_user_dep.id}: {user_doc}")

    # Convert string OIDs to ObjectId before Pydantic validation
    if "admin_manager_id" in user_doc and isinstance(user_doc["admin_manager_id"], str):
        try:
            user_doc["admin_manager_id"] = ObjectId(user_doc["admin_manager_id"])
        except Exception:
            logger.error(f"Invalid ObjectId string for admin_manager_id in require_hr_or_admin: {user_doc['admin_manager_id']}")
            pass # Let Pydantic validation fail it if it's truly invalid.
            
    if "assigned_hr_id" in user_doc and isinstance(user_doc["assigned_hr_id"], str): # For completeness
        try:
            user_doc["assigned_hr_id"] = ObjectId(user_doc["assigned_hr_id"])
        except Exception:
            pass
    
    validated_user = User.model_validate(user_doc)
    logger.debug(f"require_hr_or_admin: Validated user {validated_user.id} has role {validated_user.role} and hr_status {validated_user.hr_status if validated_user.role == 'hr' else 'N/A'}")
    return validated_user


# Candidate check (fetches full doc - reused from candidates.py logic conceptually)
async def require_candidate(current_user_dep: User = Depends(get_current_active_user)):
    """Dependency ensuring user is Candidate. Fetches full User doc."""
    if current_user_dep.role != "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted. Candidate role required.")
    db = mongodb.get_db()
    user_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": get_object_id(current_user_dep.id)})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Candidate user not found in database.")
    return User.model_validate(user_doc)
# --- End Helper Dependencies ---


@router.get("/default-questions", response_model=List[QuestionOut], tags=["Questions"])
async def get_default_questions_endpoint(db: AsyncIOMotorClient = Depends(mongodb.get_db)):
    # No changes needed here
    logger.info("Request received for default questions.")
    try:
        questions_cursor = db[settings.MONGODB_COLLECTION_QUESTIONS].find()
        questions = await questions_cursor.to_list(length=None)
        if not questions:
            logger.info("No default questions found in the database.")
            return []
        logger.info(f"Found {len(questions)} default questions.")
        return [ QuestionOut.model_validate(q) for q in questions ]
    except Exception as e:
        logger.error(f"Error fetching default questions: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch default questions.")


@router.post("/schedule", response_model=InterviewOut, status_code=status.HTTP_201_CREATED, tags=["Scheduling"])
async def schedule_interview(
    interview_data: InterviewCreate,
    # Use dependency that returns the full User model
    requesting_user: User = Depends(require_hr_or_admin),
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    """
    Schedules an interview (HR/Admin only).
    Checks if the candidate is in the 'assigned' state and if the requesting HR
    is the assigned HR (Admins bypass this specific HR check).
    """
    logger.info(f"User {requesting_user.username} attempting to schedule interview for candidate {interview_data.candidate_id}")
    candidate_resume_text: Optional[str] = None

    # --- Validate Candidate ID and Status ---
    try:
        candidate_object_id = get_object_id(str(interview_data.candidate_id))
        candidate_doc = await db[settings.MONGODB_COLLECTION_USERS].find_one(
            {"_id": candidate_object_id, "role": "candidate"}
        )
        if not candidate_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate user with ID {interview_data.candidate_id} not found.")

        # Validate candidate status
        candidate_status = candidate_doc.get("mapping_status")
        if candidate_status != "assigned":
            logger.warning(f"Scheduling denied: Candidate {interview_data.candidate_id} status is '{candidate_status}', required 'assigned'.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot schedule interview: Candidate is not in the required 'assigned' state (Current: {candidate_status})."
            )

        # Validate assigned HR (if requester is HR)
        assigned_hr_id = candidate_doc.get("assigned_hr_id")
        if not assigned_hr_id: # Should not happen if status is 'assigned', but check defensively
             logger.error(f"Data integrity issue: Candidate {candidate_object_id} has status 'assigned' but no 'assigned_hr_id'.")
             raise HTTPException(status_code=500, detail="Cannot schedule interview due to inconsistent candidate data.")

        if requesting_user.role == "hr":
             logger.info(f"HR User {requesting_user.username} attempting to schedule. Current hr_status from dependency: {requesting_user.hr_status}")
             # Ensure requesting HR is mapped
             if requesting_user.hr_status != "mapped": # Compare with the string literal "mapped"
                  logger.warning(f"HR {requesting_user.username} is not mapped. Status: {requesting_user.hr_status}")
                  raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your HR account is not currently mapped to an Admin.")
             # Check if requesting HR is the assigned HR for this candidate
             if requesting_user.id != assigned_hr_id:
                 logger.warning(f"Scheduling denied: HR {requesting_user.username} ({requesting_user.id}) is not the assigned HR ({assigned_hr_id}) for Candidate {candidate_object_id}.")
                 raise HTTPException(
                     status_code=status.HTTP_403_FORBIDDEN,
                     detail="Permission denied. You can only schedule interviews for candidates assigned to you."
                 )
        # Admins can schedule for any assigned candidate

        candidate_resume_text = candidate_doc.get("resume_text")
        logger.info(f"Candidate {candidate_object_id} validated (status: 'assigned'). Resume text found: {bool(candidate_resume_text)}")

    except HTTPException:
        raise # Re-raise validation errors
    except Exception as e:
        logger.error(f"Error validating candidate during scheduling: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing candidate details.")
    # --- End Validation ---

    # --- Question Generation (remains largely the same) ---
    logger.info(f"Generating questions for role '{interview_data.role}' and tech stack {interview_data.tech_stack}")
    generated_questions_data = []
    try:
        generated_questions_data = await gemini_service.generate_questions(
                job_title=interview_data.job_title,
                job_description=interview_data.job_description,
                num_questions=5,
                resume_text=candidate_resume_text
            )
        if generated_questions_data:
            logger.info(f"Generated {len(generated_questions_data)} questions (resume context: {bool(candidate_resume_text)}).")
        else:
            logger.warning("Gemini service returned no questions. Falling back to defaults.")
    except GeminiServiceError as e: # Catch specific Gemini error
        logger.error(f"Gemini question generation failed: {e}. Falling back to defaults.", exc_info=True)
        generated_questions_data = []
    except Exception as e: # Catch other unexpected errors
        logger.error(f"Unexpected error during Gemini question generation: {e}. Falling back to defaults.", exc_info=True)
        generated_questions_data = []


    questions = []
    if not generated_questions_data:
        logger.info("Fetching default questions from database.")
        try:
            default_questions_cursor = db[settings.MONGODB_COLLECTION_QUESTIONS].find().limit(5)
            default_questions = await default_questions_cursor.to_list(length=5)
            if default_questions:
                questions = [
                    {"question_id": str(q['_id']), "text": q.get("text", "N/A"), "category": q.get("category", "Default"), "difficulty": q.get("difficulty", "Medium")}
                    for q in default_questions
                ]
                logger.info(f"Using {len(questions)} default questions.")
            else:
                logger.error("No questions generated by LLM and no default questions found in DB.")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No questions available for interview.")
        except Exception as e:
            logger.error(f"Error accessing default questions: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error accessing default questions.")
    else:
        questions = [
            {"question_id": str(uuid4()), "text": q_data.get("text", "Generated question - text missing"), "category": q_data.get("category", "Generated"), "difficulty": q_data.get("difficulty", "Medium")}
            for q_data in generated_questions_data
        ]

    # --- Prepare and Insert Interview Document (remains largely the same) ---
    interview_doc = interview_data.model_dump(exclude={"candidate_id"}) # Exclude candidate_id from model dump as we use the validated ObjectId
    interview_doc["interview_id"] = str(uuid4())
    interview_doc["hr_id"] = requesting_user.id # Use requesting user's ObjectId
    interview_doc["candidate_id"] = candidate_object_id # Use validated candidate ObjectId
    interview_doc["status"] = "scheduled"
    interview_doc["questions"] = questions
    interview_doc["created_at"] = datetime.now(timezone.utc)
    interview_doc["updated_at"] = interview_doc["created_at"]
    # Initialize other fields
    interview_doc["overall_score"] = None
    interview_doc["overall_feedback"] = None
    interview_doc["completed_at"] = None
    interview_doc["evaluated_by"] = None
    interview_doc["evaluated_at"] = None

    try:
        result = await db[settings.MONGODB_COLLECTION_INTERVIEWS].insert_one(interview_doc)
        created_interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"_id": result.inserted_id})

        if created_interview:
            logger.info(f"Interview {created_interview['interview_id']} scheduled successfully for candidate {candidate_object_id} by user {requesting_user.username}.")
            return InterviewOut.model_validate(created_interview)
        else:
            logger.error(f"Failed to retrieve created interview with DB ID {result.inserted_id} immediately after insert.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve created interview.")
    except Exception as e:
        logger.error(f"Error inserting scheduled interview into DB: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred while scheduling interview.")

# --- Other Endpoints ---
# (Reviewing other endpoints for necessary changes based on new status fields/logic)
# - /all, /results/all: No change needed, filtering by status is fine. Access is HR/Admin.
# - /submit-response, /submit-all: Candidate action, candidate status doesn't block *submitting*, only scheduling. No change needed.
# - /candidate/me: No change needed, candidate fetches their own scheduled interviews.
# - /candidate/history: No change needed, fetches completed interviews for the candidate.
# - /results/{id}: Access check already considers candidate role. No change needed for status.
# - /{id}/results (Submit): Access is HR/Admin. No change needed for status.
# - /responses/{response_id}/evaluate: Access is HR/Admin. No change needed for status.
# - /{id}: Access check already considers candidate role. No change needed for status.
# - /{id}/responses: Access check already considers candidate role. No change needed for status.

# --- GET /all (No changes needed) ---
@router.get("/all", response_model=List[InterviewOut], tags=["Admin & HR View"])
async def get_all_interviews(
    # Dependency returns User model instance
    current_user: User = Depends(require_hr_or_admin),
    status_filter: Optional[str] = None,
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same) ...
    logger.info(f"User {current_user.username} requesting all interviews. Status filter: {status_filter}")
    query = {}
    if status_filter:
        query["status"] = status_filter
    try:
        interviews_cursor = db[settings.MONGODB_COLLECTION_INTERVIEWS].find(query)
        interviews = await interviews_cursor.to_list(length=None)
        logger.info(f"Found {len(interviews)} interviews matching filter.")
        response_list = [InterviewOut.model_validate(interview) for interview in interviews]
        return response_list
    except Exception as e:
        logger.error(f"Error fetching all interviews: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve interviews.")


# --- GET /results/all (No changes needed) ---
@router.get("/results/all", response_model=List[InterviewOut], tags=["Admin & HR View"])
async def get_all_completed_interviews(
    current_user: User = Depends(require_hr_or_admin),
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same) ...
    logger.info(f"User {current_user.username} requesting all completed interview results.")
    try:
        interviews_cursor = db[settings.MONGODB_COLLECTION_INTERVIEWS].find({"status": "completed"})
        interviews = await interviews_cursor.to_list(length=None)
        logger.info(f"Found {len(interviews)} completed interviews.")
        response_list = [InterviewOut.model_validate(interview) for interview in interviews]
        return response_list
    except Exception as e:
        logger.error(f"Error fetching all completed interviews: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve completed interviews.")

# --- POST /submit-response (No changes needed) ---
@router.post("/submit-response", response_model=InterviewResponseOut, status_code=status.HTTP_201_CREATED, tags=["Candidate Actions"])
async def submit_response(
    response_data: SingleResponseSubmit,
    candidate_user: User = Depends(require_candidate), # Fetches full User model
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same - candidate submits answer to scheduled interview) ...
    logger.info(f"Candidate {candidate_user.username} submitting single response for interview {response_data.interview_id}, question {response_data.question_id}")
    try:
        candidate_oid = candidate_user.id # Get ObjectId from User model
        logger.debug(f"submit_response: Attempting to find interview with interview_id: {response_data.interview_id}, candidate_id: {candidate_oid}")
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": response_data.interview_id, "candidate_id": candidate_oid, "status": {"$ne": "completed"}})
        
        if not interview:
            logger.error(f"submit_response: Interview not found for interview_id: {response_data.interview_id}, candidate_id: {candidate_oid}")
            # Check if it exists at all, regardless of status, for better debugging
            any_interview_status = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": response_data.interview_id, "candidate_id": candidate_oid})
            if any_interview_status:
                logger.error(f"submit_response: Interview found but status is '{any_interview_status.get('status')}'.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found, not assigned, or completed.")

        logger.debug(f"submit_response: Fetched interview doc: {interview}")
        interview_questions = interview.get("questions", [])
        logger.debug(f"submit_response: Questions from fetched interview doc: {interview_questions}")

        question_exists = any(q.get("question_id") == response_data.question_id for q in interview_questions)
        if not question_exists:
             available_ids = [q.get('question_id') for q in interview_questions]
             logger.error(f"Candidate {candidate_user.username} submitted response for non-existent question_id '{response_data.question_id}' in interview {response_data.interview_id}. Available question_ids in fetched doc: {available_ids}")
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Question ID '{response_data.question_id}' not found in this interview.")

        response_doc = {
            "interview_id": response_data.interview_id,
            "question_id": response_data.question_id,
            "answer": response_data.answer,
            "candidate_id": candidate_oid,
            "submitted_at": datetime.now(timezone.utc),
            "score": None,
            "feedback": None,
            "evaluated_by": None,
            "evaluated_at": None,
        }

        await db[settings.MONGODB_COLLECTION_RESPONSES].update_one(
            {"interview_id": response_data.interview_id, "question_id": response_data.question_id, "candidate_id": candidate_oid},
            {"$set": response_doc},
            upsert=True
        )
        saved_response = await db[settings.MONGODB_COLLECTION_RESPONSES].find_one(
            {"interview_id": response_data.interview_id, "question_id": response_data.question_id, "candidate_id": candidate_oid}
        )
        if not saved_response:
            logger.error(f"Failed to save/retrieve response for interview {response_data.interview_id}, question {response_data.question_id}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save/retrieve response.")

        total_questions = len(interview.get("questions", []))
        submitted_responses_count = await db[settings.MONGODB_COLLECTION_RESPONSES].count_documents(
            {"interview_id": response_data.interview_id, "candidate_id": candidate_oid}
        )
        logger.info(f"Interview {response_data.interview_id}: {submitted_responses_count}/{total_questions} responses recorded.")
        if submitted_responses_count >= total_questions > 0:
            completion_time = datetime.now(timezone.utc)
            await db[settings.MONGODB_COLLECTION_INTERVIEWS].update_one(
                {"_id": interview["_id"], "status": {"$ne": "completed"}},
                {"$set": {"status": "completed", "completed_at": completion_time, "updated_at": completion_time}}
            )
            logger.info(f"Interview {response_data.interview_id} marked as completed at {completion_time}.")

        return InterviewResponseOut.model_validate(saved_response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting response: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error submitting response.")

# --- POST /submit-all (No changes needed) ---
@router.post("/submit-all", status_code=status.HTTP_200_OK, tags=["Candidate Actions"])
async def submit_all_responses(
    submission: SubmitAnswersRequest,
    candidate_user: User = Depends(require_candidate), # Fetches full User model
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same - candidate submits all answers to scheduled interview) ...
    interview_id = submission.interview_id
    logger.info(f"Candidate {candidate_user.username} submitting ALL responses for interview {interview_id}.")
    try:
        candidate_oid = candidate_user.id
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({ "interview_id": interview_id, "candidate_id": candidate_oid, "status": {"$ne": "completed"} })

        if not interview:
            already_completed = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id, "candidate_id": candidate_oid, "status": "completed"})
            if already_completed:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interview already completed.")
            else:
                any_interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id, "candidate_id": candidate_oid})
                if not any_interview:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found for this candidate.")
                else:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Interview found but cannot be submitted (Status: {any_interview.get('status')}).")

        delete_filter = {"interview_id": interview_id, "candidate_id": candidate_oid}
        delete_result = await db[settings.MONGODB_COLLECTION_RESPONSES].delete_many(delete_filter)
        logger.info(f"Deleted {delete_result.deleted_count} existing responses for interview {interview_id} before inserting new ones.")

        responses_to_insert = []
        submitted_at = datetime.now(timezone.utc)
        interview_question_ids = {str(q.get("question_id")) for q in interview.get("questions", [])}

        for answer_item in submission.answers:
            question_id = answer_item.question_id
            answer_text = answer_item.answer_text

            if question_id not in interview_question_ids:
                 logger.warning(f"Skipping submitted answer for non-existent question_id '{question_id}' in interview {interview_id}.")
                 continue

            response_doc = {
                "interview_id": interview_id,
                "question_id": question_id,
                "answer": answer_text,
                "candidate_id": candidate_oid,
                "submitted_at": submitted_at,
                "score": None,
                "feedback": None,
                "evaluated_by": None,
                "evaluated_at": None,
            }
            responses_to_insert.append(response_doc)

        if responses_to_insert:
            insert_result = await db[settings.MONGODB_COLLECTION_RESPONSES].insert_many(responses_to_insert)
            logger.info(f"Inserted {len(insert_result.inserted_ids)} new responses for interview {interview_id}.")
        else:
            logger.warning(f"No valid responses provided or matched questions in the submission payload for interview {interview_id}.")

        completion_time = datetime.now(timezone.utc)
        update_result = await db[settings.MONGODB_COLLECTION_INTERVIEWS].update_one(
            {"_id": interview["_id"]},
            {"$set": {"status": "completed", "completed_at": completion_time, "updated_at": completion_time}}
        )
        if update_result.modified_count == 1:
            logger.info(f"Interview {interview_id} marked as completed at {completion_time}.")
        else:
            logger.warning(f"Failed to mark interview {interview_id} as completed (modified count: {update_result.modified_count}, matched: {update_result.matched_count}). Interview might have been completed concurrently.")

        return {"message": "Interview submitted successfully."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting all responses for interview {interview_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error submitting interview.")


# --- GET /candidate/me (No changes needed) ---
@router.get("/candidate/me", response_model=List[InterviewOut], tags=["Candidate Actions"])
async def get_my_interviews(
    candidate_user: User = Depends(require_candidate), # Fetches full User model
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same) ...
    logger.info(f"Candidate {candidate_user.username} requesting their interviews.")
    try:
        candidate_oid = candidate_user.id
        interviews_cursor = db[settings.MONGODB_COLLECTION_INTERVIEWS].find({"candidate_id": candidate_oid})
        interviews = await interviews_cursor.to_list(length=None)
        logger.info(f"Found {len(interviews)} interviews for candidate {candidate_user.username}.")
        response_list = [InterviewOut.model_validate(interview) for interview in interviews]
        return response_list
    except Exception as e:
        logger.error(f"Error fetching interviews for candidate {candidate_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve your interviews.")


# --- GET /candidate/history (No changes needed) ---
@router.get("/candidate/history", response_model=List[Dict[str, Any]], tags=["Candidate Actions"])
async def get_candidate_interview_history(
    candidate_user: User = Depends(require_candidate), # Fetches full User model
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same) ...
    logger.info(f"Fetching interview history for candidate {candidate_user.username}")
    candidate_oid = candidate_user.id
    try:
        completed_interviews_cursor = db[settings.MONGODB_COLLECTION_INTERVIEWS].find(
            {"candidate_id": candidate_oid, "status": "completed"},
            sort=[("completed_at", -1)]
        )
        completed_interviews = await completed_interviews_cursor.to_list(length=None)
        if not completed_interviews:
            logger.info(f"No completed interview history found for {candidate_user.username}.")
            return []

        interview_history = []
        interview_ids = [str(interview['interview_id']) for interview in completed_interviews]

        responses_cursor = db[settings.MONGODB_COLLECTION_RESPONSES].find(
            {"interview_id": {"$in": interview_ids}, "candidate_id": candidate_oid}
        )
        all_responses = await responses_cursor.to_list(length=None)

        responses_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for resp in all_responses:
            i_id = str(resp['interview_id'])
            q_id = str(resp['question_id'])
            if i_id not in responses_map:
                responses_map[i_id] = {}
            responses_map[i_id][q_id] = resp

        for interview in completed_interviews:
            interview_id_str = str(interview['interview_id'])
            interview_responses_for_lookup = responses_map.get(interview_id_str, {})
            questions_answers_list = []

            for question_data in interview.get("questions", []):
                q_id = str(question_data.get("question_id"))
                response_doc = interview_responses_for_lookup.get(q_id)
                questions_answers_list.append({
                    "question_id": q_id,
                    "question_text": question_data.get("text", "N/A"),
                    "answer_text": response_doc.get('answer') if response_doc else None,
                    "score": response_doc.get('score') if response_doc else None,
                    "feedback": response_doc.get('feedback') if response_doc else None
                })

            interview_history.append({
                "interview_id": interview_id_str,
                "job_title": interview.get("job_title", "N/A"),
                "role": interview.get("role", "N/A"),
                "tech_stack": interview.get("tech_stack", []),
                "completed_at": interview.get("completed_at"),
                "overall_score": interview.get("overall_score"),
                "overall_feedback": interview.get("overall_feedback"),
                "questions_details": questions_answers_list
            })

        logger.info(f"Returning history for {len(interview_history)} interviews for {candidate_user.username}.")
        return interview_history
    except Exception as e:
        logger.error(f"Error fetching history for {candidate_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve history.")

# --- GET /results/{interview_id} (No changes needed) ---
@router.get("/results/{interview_id}", response_model=InterviewResultOut, tags=["Results"])
async def get_single_interview_result(
    interview_id: str,
    # Use generic get_current_active_user, then check role inside
    current_user: User = Depends(get_current_active_user),
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same - fetches completed interview, checks role) ...
    logger.info(f"User {current_user.username} requesting result for interview {interview_id}")
    try:
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
        if not interview:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Interview {interview_id} not found.")

        if interview.get("status") != "completed":
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Interview {interview_id} is not completed yet (Status: {interview.get('status')}).")

        candidate_id_obj = interview.get("candidate_id") # Get ObjectId
        if not candidate_id_obj:
             raise HTTPException(status_code=500, detail="Interview data missing candidate ID.")

        if current_user.role == "candidate" and current_user.id != candidate_id_obj:
            logger.warning(f"Candidate {current_user.username} denied access to interview {interview_id} result (belongs to {candidate_id_obj}).")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied. You can only view your own interview results.")

        responses = await db[settings.MONGODB_COLLECTION_RESPONSES].find({"interview_id": interview_id, "candidate_id": candidate_id_obj}).to_list(length=None)
        calculated_score: Optional[float] = None
        total_score_sum = 0.0
        scored_responses_count = 0

        for r in responses:
            score = r.get("score")
            if score is not None:
                try:
                    total_score_sum += float(score)
                    scored_responses_count += 1
                except (ValueError, TypeError):
                    logger.warning(f"Invalid score format '{score}' found for response {r['_id']} in interview {interview_id}")

        if scored_responses_count > 0:
            calculated_score = total_score_sum / scored_responses_count
            logger.info(f"Calculated average score for interview {interview_id}: {calculated_score:.2f} from {scored_responses_count} scored responses.")
        else:
            logger.info(f"No scored responses found for interview {interview_id}.")

        final_score = interview.get("overall_score")
        if final_score is None:
            final_score = calculated_score

        overall_feedback_value = interview.get("overall_feedback")
        if overall_feedback_value is None:
             overall_feedback_value = "Evaluation pending." if final_score is None else "No overall feedback provided."

        logger.debug(f"Final score for interview {interview_id}: {final_score}")
        logger.debug(f"Final feedback for interview {interview_id}: {overall_feedback_value}")

        result = InterviewResultOut(
            result_id=f"result_{interview_id}",
            interview_id=interview_id,
            candidate_id=str(candidate_id_obj), # Convert ObjectId to string for response
            total_score=final_score,
            overall_feedback=overall_feedback_value,
            completed_at=interview.get("completed_at")
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching result for {interview_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve result.")

# --- POST /{interview_id}/results (No changes needed) ---
@router.post("/{interview_id}/results", response_model=InterviewOut, tags=["Results", "Admin & HR Actions"])
async def submit_interview_results(
    interview_id: str,
    result_data: InterviewResultSubmit,
    hr_or_admin_user: User = Depends(require_hr_or_admin), # Fetches full User model
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same - HR/Admin submits feedback/scores) ...
    logger.info(f"User {hr_or_admin_user.username} submitting results (incl. per-response) for interview {interview_id}")
    try:
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
        if not interview:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Interview {interview_id} not found.")
        if interview.get("status") != "completed":
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot submit results: interview not completed.")

        interview_oid = interview["_id"]
        candidate_oid = interview["candidate_id"] # Should be ObjectId

        if result_data.responses_feedback:
            logger.info(f"Processing {len(result_data.responses_feedback)} individual response feedbacks for interview {interview_id}.")
            updated_response_count = 0
            for resp_feedback in result_data.responses_feedback:
                response_update_data = {}
                if resp_feedback.score is not None: response_update_data["score"] = resp_feedback.score
                if resp_feedback.feedback is not None: response_update_data["feedback"] = resp_feedback.feedback

                if response_update_data:
                    response_update_data["evaluated_by"] = hr_or_admin_user.username
                    response_update_data["evaluated_at"] = datetime.now(timezone.utc)

                    resp_update_result = await db[settings.MONGODB_COLLECTION_RESPONSES].update_one(
                        {"interview_id": interview_id, "candidate_id": candidate_oid, "question_id": resp_feedback.question_id},
                        {"$set": response_update_data}
                    )
                    if resp_update_result.matched_count == 0:
                        logger.warning(f"No matching response found for question_id '{resp_feedback.question_id}' in interview {interview_id} to apply feedback.")
                    elif resp_update_result.modified_count > 0:
                        updated_response_count += 1
            logger.info(f"Updated score/feedback for {updated_response_count} individual responses in interview {interview_id}.")

        calculated_overall_score: Optional[float] = None
        all_responses = await db[settings.MONGODB_COLLECTION_RESPONSES].find(
            {"interview_id": interview_id, "candidate_id": candidate_oid, "score": {"$ne": None}}
        ).to_list(length=None)

        if all_responses:
             total_score_sum = 0.0
             scored_responses_count = 0
             for r in all_responses:
                 score = r.get("score")
                 try:
                     total_score_sum += float(score)
                     scored_responses_count += 1
                 except (ValueError, TypeError):
                     logger.warning(f"Invalid score format '{score}' found for scored response {r['_id']} during overall calculation.")

             if scored_responses_count > 0:
                 calculated_overall_score = total_score_sum / scored_responses_count
             logger.info(f"Recalculated overall score for interview {interview_id}: {calculated_overall_score}")
        else:
             logger.info(f"No scored responses found after update for interview {interview_id}.")

        current_time = datetime.now(timezone.utc)
        interview_update_data = {
            "evaluated_by": hr_or_admin_user.username,
            "evaluated_at": current_time,
            "updated_at": current_time
        }

        if result_data.overall_score is not None:
            interview_update_data["overall_score"] = result_data.overall_score
            logger.info(f"Using manually submitted overall score ({result_data.overall_score}) for interview {interview_id}.")
        elif calculated_overall_score is not None:
             interview_update_data["overall_score"] = calculated_overall_score
             logger.info(f"Using calculated overall score ({calculated_overall_score}) for interview {interview_id}.")
        elif "overall_score" not in interview_update_data:
             logger.info(f"No manual overall score submitted and none could be calculated for interview {interview_id}.")

        if result_data.overall_feedback is not None:
            interview_update_data["overall_feedback"] = result_data.overall_feedback
            logger.info(f"Applying submitted overall feedback for interview {interview_id}.")

        update_result = await db[settings.MONGODB_COLLECTION_INTERVIEWS].update_one(
            {"_id": interview_oid},
            {"$set": interview_update_data}
        )
        if update_result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found during final update.")
        if update_result.modified_count == 0:
            logger.warning(f"Interview {interview_id} overall results were not modified (perhaps submitted data was identical?).")
        else:
            logger.info(f"Successfully submitted/updated overall results info for interview {interview_id} by user {hr_or_admin_user.username}.")

        updated_interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"_id": interview_oid})
        if not updated_interview:
            logger.error(f"Failed to retrieve interview {interview_id} after submitting results.")
            raise HTTPException(status_code=500, detail="Failed to retrieve updated interview after submitting results.")

        return InterviewOut.model_validate(updated_interview)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting results for interview {interview_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while submitting interview results.")


# --- POST /responses/{response_id}/evaluate (No changes needed) ---
@router.post("/responses/{response_id}/evaluate", response_model=Dict) # Return dict as before
async def evaluate_single_response_ai(
    response_id: str,
    hr_or_admin_user: User = Depends(require_hr_or_admin), # Fetches full User model
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same - HR/Admin triggers AI eval) ...
    logger.info(f"User {hr_or_admin_user.username} triggering AI evaluation for response ID: {response_id}")
    try:
        try: response_oid = get_object_id(response_id)
        except HTTPException as e: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid response ID format: {response_id}")

        response_doc = await db[settings.MONGODB_COLLECTION_RESPONSES].find_one({"_id": response_oid})
        if not response_doc: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response not found.")

        required_fields = ["answer", "question_id", "interview_id"]
        missing_fields = [field for field in required_fields if not response_doc.get(field)]
        if missing_fields: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Response data incomplete. Missing fields: {', '.join(missing_fields)}")

        answer_text = response_doc["answer"]
        question_id = response_doc["question_id"]
        interview_id = response_doc["interview_id"]

        if not answer_text or len(answer_text.strip()) < 10: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answer must be at least 10 characters long for AI evaluation.")

        interview_doc = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
        if not interview_doc: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated interview not found.")

        question_text = None
        for q in interview_doc.get("questions", []):
            if str(q.get("question_id")) == str(question_id):
                question_text = q.get("text")
                break
        if not question_text: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corresponding question text not found in interview data.")

        logger.info(f"Calling Gemini service to evaluate response {response_id}...")
        try:
            evaluation_result = await gemini_service.evaluate_answer(
                question_text=question_text, answer_text=answer_text,
                job_title=interview_doc.get("job_title"), job_description=interview_doc.get("job_description")
            )
        except GeminiServiceError as e: # Catch specific Gemini error
            logger.error(f"AI evaluation service failed for response {response_id}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI evaluation service failed: {e}")
        except Exception as e: # Catch other unexpected errors
            logger.error(f"Unexpected error during AI evaluation call for response {response_id}: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI evaluation service encountered an unexpected error.")


        if not isinstance(evaluation_result, dict): raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid evaluation result format from AI service.")

        required_eval_fields = ["score", "feedback"]
        missing_eval_fields = [field for field in required_eval_fields if field not in evaluation_result]
        if missing_eval_fields: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AI evaluation incomplete. Missing fields: {', '.join(missing_eval_fields)}")

        ai_score = evaluation_result["score"]
        ai_feedback = evaluation_result["feedback"]
        try:
            ai_score = float(ai_score); assert 0 <= ai_score <= 5
        except (ValueError, TypeError, AssertionError): raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid score format or range from AI evaluation.")

        current_time = datetime.now(timezone.utc)
        update_data = {
            "score": ai_score, "feedback": f"[AI]: {ai_feedback}",
            "evaluated_by": f"AI ({hr_or_admin_user.username})", "evaluated_at": current_time
        }
        try:
            update_result = await db[settings.MONGODB_COLLECTION_RESPONSES].update_one({"_id": response_oid}, {"$set": update_data})
        except Exception as e: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update response with evaluation results.")

        if update_result.matched_count == 0: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response not found during update.")
        if update_result.modified_count == 0: logger.warning(f"Response {response_id} score/feedback was not modified by AI evaluation.")

        updated_response_doc = await db[settings.MONGODB_COLLECTION_RESPONSES].find_one({"_id": response_oid})
        if not updated_response_doc: raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve updated response after AI evaluation.")
        
        response_out = InterviewResponseOut.model_validate(updated_response_doc)
        response_dict = response_out.model_dump() 

        # The key 'id' should already be in response_dict due to InterviewResponseOut schema (via PyObjectIdStr)
        # The pop('_id') line was causing a KeyError if model_dump() already converted _id to id.
        # This check ensures 'id' is present and a string, which it should be.
        if 'id' not in response_dict or not isinstance(response_dict.get('id'), str):
             logger.error(f"Serialization issue: 'id' field missing or not string in response_dict for {response_oid}. Dict: {response_dict}")
             # Fallback or raise error, depending on desired strictness
             response_dict['id'] = str(response_oid) # Ensure 'id' is present as string if missing
        
        return response_dict
    except HTTPException: raise
    except Exception as e: logger.error(f"Unexpected error evaluating response {response_id}: {str(e)}", exc_info=True); raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during AI evaluation.")


# --- GET /{interview_id} (No changes needed) ---
@router.get("/{interview_id}", response_model=InterviewOut, tags=["Details"])
async def get_interview_details(
    interview_id: str,
    current_user: User = Depends(get_current_active_user), # Use generic dependency
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same - checks role inside) ...
    logger.info(f"User {current_user.username} requesting details for interview {interview_id}")
    try:
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
        if not interview: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")

        candidate_id_obj = interview.get("candidate_id")
        if not candidate_id_obj: raise HTTPException(status_code=500, detail="Interview data missing candidate ID.")

        if current_user.role == "candidate" and current_user.id != candidate_id_obj:
             logger.warning(f"Candidate {current_user.username} denied access to interview {interview_id} details (belongs to {candidate_id_obj}).")
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

        return InterviewOut.model_validate(interview)
    except HTTPException: raise
    except Exception as e: logger.error(f"Error fetching details for {interview_id}: {e}", exc_info=True); raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve details.")

# --- GET /{interview_id}/responses (No changes needed) ---
@router.get("/{interview_id}/responses", response_model=List[InterviewResponseOut], tags=["Details"])
async def get_interview_responses_list(
    interview_id: str,
    current_user: User = Depends(get_current_active_user), # Use generic dependency
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # ... (implementation remains the same - checks role inside) ...
    logger.info(f"User {current_user.username} requesting responses for interview {interview_id}")
    try:
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
        if not interview: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")

        candidate_id_obj = interview.get("candidate_id")
        if not candidate_id_obj: raise HTTPException(status_code=500, detail="Interview data missing candidate ID.")

        if current_user.role == "candidate" and current_user.id != candidate_id_obj:
            logger.warning(f"Candidate {current_user.username} denied access to interview {interview_id} responses (belongs to {candidate_id_obj}).")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

        responses_cursor = db[settings.MONGODB_COLLECTION_RESPONSES].find({"interview_id": interview_id})
        responses = await responses_cursor.to_list(length=None)
        logger.info(f"Found {len(responses)} responses for interview {interview_id}")

        response_list = [InterviewResponseOut.model_validate(response) for response in responses]
        return response_list
    except HTTPException: raise
    except Exception as e: logger.error(f"Error fetching responses for {interview_id}: {e}", exc_info=True); raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve responses.")
