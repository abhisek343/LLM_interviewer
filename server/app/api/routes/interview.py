# LLM_interviewer/server/app/api/routes/interview.py

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from app.schemas.interview import (
    QuestionOut, InterviewCreate, InterviewOut,
    InterviewResponseCreate, InterviewResponseOut,
    InterviewResultOut, SubmitAnswersRequest, AnswerItem, # Added AnswerItem for clarity
    InterviewResultSubmit # Corrected schema name
)
# Using security functions directly for clarity
from app.core.security import get_current_active_user
# Import User model and UserRole for role checks
from app.models.user import User # Keep User model for dependency type hint
# Import UserOut for response models where appropriate (like current_user)
from app.schemas.user import UserOut # Keep UserOut if used, otherwise User is fine for Depends
from app.db.mongodb import mongodb
from app.core.config import settings # Import settings for collection names
from app.services.gemini_service import gemini_service # Import gemini_service
from uuid import uuid4
from datetime import datetime
from bson import ObjectId # Import ObjectId
from bson.errors import InvalidId # Import InvalidId for error handling
from motor.motor_asyncio import AsyncIOMotorClient # Import AsyncIOMotorClient for type hint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["Interview"])

# --- Helper function to Get ObjectId ---
def get_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError) as e:
        logger.error(f"Invalid ObjectId format: '{id_str}'. Error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ID format: {id_str}")

# --- Helper Dependencies for Role Checks ---
async def require_hr_or_admin(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in ["hr", "admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted. HR or Admin privileges required.")
    return current_user

async def require_candidate(current_user: User = Depends(get_current_active_user)):
    if current_user.role != "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted. Candidate role required.")
    return current_user
# --- End Helper Dependencies ---


@router.get("/default-questions", response_model=List[QuestionOut], tags=["Questions"])
async def get_default_questions_endpoint(db: AsyncIOMotorClient = Depends(mongodb.get_db)):
    # (Code remains the same)
    logger.info("Request received for default questions.")
    try:
        questions_cursor = db[settings.MONGODB_COLLECTION_QUESTIONS].find()
        questions = await questions_cursor.to_list(length=10)
        if not questions:
            return []
        # Ensure _id is converted to question_id string for QuestionOut schema
        return [ QuestionOut(**q, question_id=str(q['_id'])) for q in questions ]
    except Exception as e:
        logger.error(f"Error fetching default questions: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch default questions.")


@router.post("/schedule", response_model=InterviewOut, status_code=status.HTTP_201_CREATED, tags=["Scheduling"])
async def schedule_interview(
    interview_data: InterviewCreate, hr_user: User = Depends(require_hr_or_admin), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # (Code remains the same - assuming InterviewCreate schema is correct)
    logger.info(f"User {hr_user.username} scheduling interview for candidate {interview_data.candidate_id}")
    candidate_resume_text: Optional[str] = None
    try:
        candidate_object_id = get_object_id(interview_data.candidate_id)
        # hr_object_id = get_object_id(hr_user.id) # Get hr_id from the dependency result
    except HTTPException as e:
        raise e # Re-raise validation error from get_object_id

    # Verify candidate exists
    candidate = await db[settings.MONGODB_COLLECTION_USERS].find_one({"_id": candidate_object_id, "role": "candidate"})
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate user with ID {interview_data.candidate_id} not found.")
    else:
        candidate_resume_text = candidate.get("resume_text")
        logger.info(f"Resume text found for candidate {candidate['_id']}: {bool(candidate_resume_text)}")

    logger.info(f"Generating questions for role '{interview_data.role}' and tech stack {interview_data.tech_stack}")
    generated_questions_data = []
    try:
        # Call Gemini service using fields from InterviewCreate schema
        generated_questions_data = await gemini_service.generate_questions(
                job_title=interview_data.job_title, # Use job_title from InterviewCreate
                job_description=interview_data.job_description, # Use job_description from InterviewCreate
                num_questions=5, # Or make this configurable/part of request
                # category=... # Optional: Pass if needed
                # difficulty=... # Optional: Pass if needed
                resume_text=candidate_resume_text
            )
        if generated_questions_data:
            logger.info(f"Generated {len(generated_questions_data)} questions (resume context: {bool(candidate_resume_text)}).")
        else:
            logger.warning("Gemini service returned no questions. Falling back to defaults.")
    except Exception as e:
        logger.error(f"Gemini question generation failed: {e}. Falling back to defaults.", exc_info=True)
        generated_questions_data = [] # Ensure it's an empty list on error

    questions = []
    if not generated_questions_data:
        logger.info("Fetching default questions from database.")
        try:
            default_questions_cursor = db[settings.MONGODB_COLLECTION_QUESTIONS].find()
            default_questions = await default_questions_cursor.to_list(length=5) # Limit default questions
            if default_questions:
                # Convert default questions (from DB) to the expected format for embedding
                questions = [
                    {
                        "question_id": str(q['_id']), # Use DB _id as question_id
                        "text": q.get("text", "N/A"),
                        "category": q.get("category", "Default"),
                        "difficulty": q.get("difficulty", "Medium")
                    }
                    for q in default_questions
                ]
                logger.info(f"Using {len(questions)} default questions.")
            else:
                logger.error("No questions generated by LLM and no default questions found in DB.")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No questions generated and no defaults available.")
        except Exception as e:
            logger.error(f"Error accessing default questions: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error accessing default questions.")
    else:
        # Process generated questions (ensure they match the embedded structure)
        questions_for_db = []
        for q_data in generated_questions_data:
            # Assuming q_data is a dict like {"text": ..., "category": ..., "difficulty": ...}
            question_doc = {
                "question_id": str(uuid4()), # Generate a new UUID for embedded questions
                "text": q_data.get("text", "N/A"),
                "category": q_data.get("category", "Generated"),
                "difficulty": q_data.get("difficulty", "Medium"),
            }
            questions_for_db.append(question_doc)
        questions = questions_for_db

    # Prepare the interview document for insertion
    # Exclude hr_id as it's set server-side
    interview_doc = interview_data.model_dump(exclude={"hr_id"})
    interview_doc["interview_id"] = str(uuid4()) # Generate unique interview session ID
    interview_doc["hr_id"] = get_object_id(hr_user.id) # Set hr_id from the authenticated user dependency
    interview_doc["status"] = "scheduled"
    interview_doc["questions"] = questions # Embed the prepared questions list
    interview_doc["created_at"] = datetime.utcnow()
    interview_doc["candidate_id"] = candidate_object_id # Use the validated ObjectId
    # Initialize result fields
    interview_doc["overall_score"] = None
    interview_doc["overall_feedback"] = None
    interview_doc["completed_at"] = None
    interview_doc["evaluated_by"] = None
    interview_doc["evaluated_at"] = None

    try:
        result = await db[settings.MONGODB_COLLECTION_INTERVIEWS].insert_one(interview_doc)
        # Fetch the created document using its _id
        created_interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"_id": result.inserted_id})

        if created_interview:
            # Prepare for InterviewOut response
            logger.debug(f"Fetched created_interview from DB. Keys: {created_interview.keys()}")
            logger.debug(f"Questions in fetched doc: {created_interview.get('questions')}")
            # Validate and return using InterviewOut schema
            # Pydantic validation will handle aliasing _id to id if defined in InterviewOut
            return InterviewOut.model_validate(created_interview)
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve created interview.")
    except Exception as e:
        logger.error(f"Error inserting scheduled interview into DB: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred while scheduling interview.")


@router.get("/all", response_model=List[InterviewOut], tags=["Admin & HR View"])
async def get_all_interviews(
    current_user: User = Depends(require_hr_or_admin), status_filter: Optional[str] = None, db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # (Code remains the same)
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

@router.get("/results/all", response_model=List[InterviewOut], tags=["Admin & HR View"])
async def get_all_completed_interviews(
    current_user: User = Depends(require_hr_or_admin), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # (Code remains the same)
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

@router.post("/submit-response", response_model=InterviewResponseOut, status_code=status.HTTP_201_CREATED, tags=["Candidate Actions"])
async def submit_response(
    response_data: InterviewResponseCreate, candidate_user: User = Depends(require_candidate), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # (Code remains the same)
    logger.info(f"Candidate {candidate_user.username} submitting single response for interview {response_data.interview_id}, question {response_data.question_id}")
    try:
        candidate_oid = get_object_id(candidate_user.id)
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": response_data.interview_id, "candidate_id": candidate_oid, "status": {"$ne": "completed"}})
        if not interview:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found, not assigned, or completed.")
        response_doc = response_data.model_dump()
        response_doc["candidate_id"] = candidate_oid
        response_doc["submitted_at"] = datetime.utcnow()
        response_doc["score"] = None
        response_doc["feedback"] = None
        # Upsert the response
        await db[settings.MONGODB_COLLECTION_RESPONSES].update_one( {"interview_id": response_data.interview_id, "question_id": response_data.question_id, "candidate_id": candidate_oid}, {"$set": response_doc}, upsert=True)
        saved_response = await db[settings.MONGODB_COLLECTION_RESPONSES].find_one({"interview_id": response_data.interview_id, "question_id": response_data.question_id, "candidate_id": candidate_oid})
        if not saved_response:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save/retrieve response.")
        # Check if all questions are answered to mark interview complete
        total_questions = len(interview.get("questions", []))
        submitted_responses_count = await db[settings.MONGODB_COLLECTION_RESPONSES].count_documents({"interview_id": response_data.interview_id, "candidate_id": candidate_oid})
        logger.info(f"Interview {response_data.interview_id}: {submitted_responses_count}/{total_questions} responses recorded.")
        if submitted_responses_count >= total_questions > 0:
            await db[settings.MONGODB_COLLECTION_INTERVIEWS].update_one( {"_id": interview["_id"], "status": {"$ne": "completed"}}, {"$set": {"status": "completed", "completed_at": datetime.utcnow()}} )
            logger.info(f"Interview {response_data.interview_id} marked as completed.")
        # Prepare response
        # Pydantic model validation will handle alias _id -> response_id
        return InterviewResponseOut.model_validate(saved_response)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting response: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error submitting response.")

# --- Endpoint with Correction ---
@router.post("/submit-all", status_code=status.HTTP_200_OK, tags=["Candidate Actions"])
async def submit_all_responses(
    submission: SubmitAnswersRequest, candidate_user: User = Depends(require_candidate), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    interview_id = submission.interview_id
    logger.info(f"Candidate {candidate_user.username} submitting ALL responses for interview {interview_id}.")
    try:
        candidate_oid = get_object_id(candidate_user.id)
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({ "interview_id": interview_id, "candidate_id": candidate_oid, "status": {"$ne": "completed"} })

        if not interview:
            already_completed = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id, "candidate_id": candidate_oid, "status": "completed"})
            if already_completed:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interview already completed.")
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found or cannot be submitted.")

        # Delete existing responses for this interview/candidate before bulk insert
        delete_filter = {"interview_id": interview_id, "candidate_id": candidate_oid}
        delete_result = await db[settings.MONGODB_COLLECTION_RESPONSES].delete_many(delete_filter)
        logger.info(f"Deleted {delete_result.deleted_count} existing responses for interview {interview_id} before inserting new ones.")

        # Prepare responses for bulk insertion
        responses_to_insert = []
        submitted_at = datetime.utcnow()

        # --- MODIFIED LOOP: Access Pydantic model attributes directly ---
        for answer_item in submission.answers: # Iterate through AnswerItem objects
            # Access attributes directly using dot notation
            question_id = answer_item.question_id
            answer_text = answer_item.answer_text

            # Pydantic validation usually ensures these are not None if they are mandatory fields
            # No need for the 'is None' check here unless they are Optional in AnswerItem

            response_doc = {
                "interview_id": interview_id,
                "question_id": question_id, # Use the variable
                "answer": answer_text,      # Store the text under the 'answer' key for the DB
                "candidate_id": candidate_oid,
                "submitted_at": submitted_at,
                "score": None,
                "feedback": None
            }
            responses_to_insert.append(response_doc)
        # --- END MODIFIED LOOP ---

        # Bulk insert
        if responses_to_insert:
            insert_result = await db[settings.MONGODB_COLLECTION_RESPONSES].insert_many(responses_to_insert)
            logger.info(f"Inserted {len(insert_result.inserted_ids)} new responses for interview {interview_id}.")
        else:
            logger.warning(f"No valid responses provided in the submission payload for interview {interview_id}.")

        # Mark interview as completed
        completion_time = datetime.utcnow()
        update_result = await db[settings.MONGODB_COLLECTION_INTERVIEWS].update_one(
            {"_id": interview["_id"]},
            {"$set": {"status": "completed", "completed_at": completion_time}}
        )
        if update_result.modified_count == 1:
            logger.info(f"Interview {interview_id} marked as completed at {completion_time}.")
        else:
            # Maybe the status was already 'completed'? Log as warning.
            logger.warning(f"Failed to mark interview {interview_id} as completed (modified count: {update_result.modified_count}, matched: {update_result.matched_count}).")

        return {"message": "Interview submitted successfully."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting all responses for interview {interview_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error submitting interview.")
# --- End Endpoint with Correction ---


@router.get("/candidate/me", response_model=List[InterviewOut], tags=["Candidate Actions"])
async def get_my_interviews(
    candidate_user: User = Depends(require_candidate), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # (Code remains the same)
    logger.info(f"Candidate {candidate_user.username} requesting their interviews.")
    try:
        candidate_oid = get_object_id(candidate_user.id)
        interviews_cursor = db[settings.MONGODB_COLLECTION_INTERVIEWS].find({"candidate_id": candidate_oid})
        interviews = await interviews_cursor.to_list(length=None)
        logger.info(f"Found {len(interviews)} interviews for candidate {candidate_user.username}.")
        response_list = [InterviewOut.model_validate(interview) for interview in interviews]
        return response_list
    except Exception as e:
        logger.error(f"Error fetching interviews for candidate {candidate_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve your interviews.")

@router.get("/candidate/history", response_model=List[Dict[str, Any]], tags=["Candidate Actions"])
async def get_candidate_interview_history(
    candidate_user: User = Depends(require_candidate), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # (Code remains the same)
    logger.info(f"Fetching interview history for candidate {candidate_user.username}")
    candidate_oid = get_object_id(candidate_user.id)
    try:
        completed_interviews_cursor = db[settings.MONGODB_COLLECTION_INTERVIEWS].find({"candidate_id": candidate_oid, "status": "completed"}, sort=[("completed_at", -1)])
        completed_interviews = await completed_interviews_cursor.to_list(length=None)
        if not completed_interviews:
            return []
        interview_history = []
        interview_ids = [str(interview['interview_id']) for interview in completed_interviews]
        responses_cursor = db[settings.MONGODB_COLLECTION_RESPONSES].find({"interview_id": {"$in": interview_ids}, "candidate_id": candidate_oid})
        all_responses = await responses_cursor.to_list(length=None)
        responses_map: Dict[str, Dict[str, str]] = {}
        for resp in all_responses:
            i_id = str(resp['interview_id'])
            q_id = str(resp['question_id'])
            answer = resp.get('answer', '') # Uses 'answer' key, consistent with corrected insert
            if i_id not in responses_map:
                responses_map[i_id] = {}
            responses_map[i_id][q_id] = answer
        for interview in completed_interviews:
            interview_id_str = str(interview['interview_id'])
            interview_responses = responses_map.get(interview_id_str, {})
            questions_answers_list = []
            for question_data in interview.get("questions", []):
                q_id = str(question_data.get("question_id"))
                answer_text = interview_responses.get(q_id) # Fetch based on q_id from map
                questions_answers_list.append({"question_text": question_data.get("text", "N/A"), "answer_text": answer_text})
            interview_history.append({ "interview_id": interview_id_str, "role": interview.get("role", "N/A"), "tech_stack": interview.get("tech_stack", []), "completed_at": interview.get("completed_at"), "questions_answers": questions_answers_list })
        logger.info(f"Returning history for {len(interview_history)} interviews for {candidate_user.username}.")
        return interview_history
    except Exception as e:
        logger.error(f"Error fetching history for {candidate_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve history.")

# --- MODIFIED Endpoint: Get Single Result (Calculates overall score) ---
# Note: This endpoint calculation logic might need review depending on how scores are intended to be set
@router.get("/results/{interview_id}", response_model=InterviewResultOut, tags=["Results"])
async def get_single_interview_result(
    interview_id: str, current_user: User = Depends(get_current_active_user), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    """
    Retrieves the result for a specific completed interview.
    Calculates the overall score based on available individual response scores,
    unless an overall score was manually submitted.
    """
    logger.info(f"User {current_user.username} requesting result for interview {interview_id}")
    try:
        # Find the completed interview
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id, "status": "completed"})
        if not interview:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Completed interview {interview_id} not found.")

        candidate_id_str = str(interview.get("candidate_id"))
        # Permission check
        if current_user.role == "candidate" and str(current_user.id) != candidate_id_str: # Compare string IDs
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

        # Fetch all responses for this interview to calculate score
        responses = await db[settings.MONGODB_COLLECTION_RESPONSES].find({"interview_id": interview_id, "candidate_id": interview["candidate_id"]}).to_list(length=None)

        calculated_score: Optional[float] = None
        total_score_sum = 0
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


        # Determine final score: Use manually submitted overall score if available, else use calculated average
        final_score = interview.get("overall_score") # Check if manual score exists on interview doc
        if final_score is None:
            final_score = calculated_score # Use calculated score if no manual score

        # Get overall feedback (likely manually submitted)
        overall_feedback = interview.get("overall_feedback", "Evaluation pending." if final_score is None else "No overall feedback provided.")

        # Construct result response
        result = InterviewResultOut(
            result_id=f"result_{interview_id}",
            interview_id=interview_id,
            candidate_id=candidate_id_str,
            total_score=final_score, # Use determined final score (manual or calculated)
            overall_feedback=overall_feedback,
            completed_at=interview.get("completed_at")
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching result for {interview_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve result.")

# --- MODIFIED Endpoint: Submit Results (Calculates and stores overall score) ---
# Note: This endpoint calculation logic might need review
@router.post("/{interview_id}/results", response_model=InterviewOut, tags=["Results", "Admin & HR Actions"])
async def submit_interview_results(
    interview_id: str, result_data: InterviewResultSubmit, hr_or_admin_user: User = Depends(require_hr_or_admin), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    """
    Allows HR or Admin to submit overall score/feedback AND/OR per-response scores/feedback.
    Calculates and stores the overall score based on individual scores unless overridden.
    """
    logger.info(f"User {hr_or_admin_user.username} submitting results (incl. per-response) for interview {interview_id}")
    try:
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id, "status": "completed"})
        if not interview:
            not_completed = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
            if not_completed:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot submit results: interview not completed.")
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Completed interview not found.")
        interview_oid = interview["_id"]
        candidate_oid = interview["candidate_id"]

        # 1. Update individual responses if feedback is provided
        if result_data.responses_feedback:
            logger.info(f"Processing {len(result_data.responses_feedback)} individual response feedbacks for interview {interview_id}.")
            updated_response_count = 0
            # Consider using bulk write for efficiency
            for resp_feedback in result_data.responses_feedback:
                response_update_data = {}
                if resp_feedback.score is not None:
                    response_update_data["score"] = resp_feedback.score
                if resp_feedback.feedback is not None:
                    response_update_data["feedback"] = resp_feedback.feedback
                if response_update_data:
                    resp_update_result = await db[settings.MONGODB_COLLECTION_RESPONSES].update_one( {"interview_id": interview_id, "candidate_id": candidate_oid, "question_id": resp_feedback.question_id}, {"$set": response_update_data} )
                    if resp_update_result.matched_count == 0:
                        logger.warning(f"No matching response found for question_id '{resp_feedback.question_id}' in interview {interview_id} to apply feedback.")
                    elif resp_update_result.modified_count > 0:
                        updated_response_count += 1
            logger.info(f"Updated score/feedback for {updated_response_count} individual responses in interview {interview_id}.")

        # 2. Recalculate overall score based on potentially updated responses
        calculated_overall_score: Optional[float] = None
        all_responses = await db[settings.MONGODB_COLLECTION_RESPONSES].find({"interview_id": interview_id, "candidate_id": candidate_oid}).to_list(length=None)
        if all_responses:
             total_score_sum = 0
             scored_responses_count = 0
             for r in all_responses:
                 score = r.get("score")
                 if score is not None:
                     try:
                         total_score_sum += float(score)
                         scored_responses_count += 1
                     except (ValueError, TypeError):
                         logger.warning(f"Invalid score format '{score}' found for response {r['_id']} during overall calculation.")
             if scored_responses_count > 0:
                 calculated_overall_score = total_score_sum / scored_responses_count
             logger.info(f"Recalculated overall score for interview {interview_id}: {calculated_overall_score}")

        # 3. Prepare update data for the main interview document
        interview_update_data = {"evaluated_by": hr_or_admin_user.username, "evaluated_at": datetime.utcnow()}
        # Use manually submitted overall score if provided, otherwise use calculated score
        if result_data.overall_score is not None:
            interview_update_data["overall_score"] = result_data.overall_score
            logger.info(f"Using manually submitted overall score ({result_data.overall_score}) for interview {interview_id}.")
        elif calculated_overall_score is not None:
             interview_update_data["overall_score"] = calculated_overall_score
             logger.info(f"Using calculated overall score ({calculated_overall_score}) for interview {interview_id}.")
        # Include overall feedback if provided
        if result_data.overall_feedback is not None:
            interview_update_data["overall_feedback"] = result_data.overall_feedback

        # 4. Update the interview document
        if len(interview_update_data) > 2: # Only update if score/feedback was added
             update_result = await db[settings.MONGODB_COLLECTION_INTERVIEWS].update_one({"_id": interview_oid}, {"$set": interview_update_data})
             if update_result.matched_count == 0:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found during final update.")
             if update_result.modified_count == 0:
                 logger.warning(f"Interview {interview_id} overall results were not modified.")
             else:
                 logger.info(f"Successfully submitted/updated overall results info for interview {interview_id} by user {hr_or_admin_user.username}.")
        else:
            logger.info(f"No overall score/feedback submitted for interview {interview_id} (only individual responses may have been updated).")

        # 5. Fetch and return the updated interview document
        updated_interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"_id": interview_oid})
        if not updated_interview:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated interview after submitting results.")

        return InterviewOut.model_validate(updated_interview)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting results for interview {interview_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while submitting interview results.")


@router.post("/responses/{response_id}/evaluate", response_model=InterviewResponseOut, tags=["Results", "Admin & HR Actions"])
async def evaluate_single_response_ai(
    response_id: str,
    hr_or_admin_user: User = Depends(require_hr_or_admin),
    db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # (Code remains the same)
    """
    Evaluates a single interview response using AI.
    Validates the response data, retrieves the associated question,
    calls the Gemini service for evaluation, and updates the response with the results.
    """
    logger.info(f"User {hr_or_admin_user.username} triggering AI evaluation for response ID: {response_id}")

    try:
        # Validate response_id format
        try:
            response_oid = get_object_id(response_id)
        except HTTPException as e:
            logger.error(f"Invalid response ID format: {response_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid response ID format: {response_id}"
            )

        # Retrieve and validate response document
        response_doc = await db[settings.MONGODB_COLLECTION_RESPONSES].find_one({"_id": response_oid})
        if not response_doc:
            logger.error(f"Response not found: {response_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Response not found."
            )

        # Validate required fields in response
        required_fields = ["answer", "question_id", "interview_id"]
        missing_fields = [field for field in required_fields if not response_doc.get(field)]
        if missing_fields:
            logger.error(f"Missing required fields in response {response_id}: {missing_fields}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Response data incomplete. Missing fields: {', '.join(missing_fields)}"
            )

        answer_text = response_doc["answer"] # Use 'answer' key here as it's stored that way
        question_id = response_doc["question_id"]
        interview_id = response_doc["interview_id"]

        # Validate answer text
        if len(answer_text.strip()) < 10: # Example minimum length
            logger.error(f"Answer too short in response {response_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answer must be at least 10 characters long."
            )

        # Retrieve and validate interview document
        interview_doc = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
        if not interview_doc:
            logger.error(f"Associated interview not found for response {response_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated interview not found."
            )

        # Find and validate question text
        question_text = None
        for q in interview_doc.get("questions", []):
            if str(q.get("question_id")) == str(question_id):
                question_text = q.get("text")
                break

        if not question_text:
            logger.error(f"Question text not found for response {response_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Corresponding question text not found."
            )

        # Call Gemini service for evaluation
        logger.info(f"Calling Gemini service to evaluate response {response_id}...")
        try:
            evaluation_result = await gemini_service.evaluate_answer(
                question_text=question_text,
                answer_text=answer_text # Pass the candidate's answer
            )
        except Exception as e:
            logger.error(f"Gemini service evaluation failed for response {response_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI evaluation service failed. Please try again later."
            )

        # Validate evaluation result
        if not isinstance(evaluation_result, dict):
            logger.error(f"Invalid evaluation result format for response {response_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid evaluation result format from AI service."
            )

        required_eval_fields = ["score", "feedback"]
        missing_eval_fields = [field for field in required_eval_fields if field not in evaluation_result]
        if missing_eval_fields:
            logger.error(f"Missing required fields in evaluation result for response {response_id}: {missing_eval_fields}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI evaluation incomplete. Missing fields: {', '.join(missing_eval_fields)}"
            )

        ai_score = evaluation_result["score"]
        ai_feedback = evaluation_result["feedback"]

        # Validate score format and range
        try:
            ai_score = float(ai_score)
            if not 0 <= ai_score <= 5: # Adjust range if needed
                 raise ValueError("Score out of range")
        except (ValueError, TypeError):
            logger.error(f"Invalid score format/range in evaluation result for response {response_id}: {ai_score}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid score format or range from AI evaluation."
            )

        # Prepare update data
        update_data = {
            "score": ai_score,
            "feedback": f"[AI]: {ai_feedback}",
            "evaluated_by": f"AI ({hr_or_admin_user.username})", # Note who triggered AI eval
            "evaluated_at": datetime.utcnow()
        }

        # Update response document
        try:
            update_result = await db[settings.MONGODB_COLLECTION_RESPONSES].update_one(
                {"_id": response_oid},
                {"$set": update_data}
            )
        except Exception as e:
            logger.error(f"Failed to update response {response_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update response with evaluation results."
            )

        if update_result.matched_count == 0:
            logger.error(f"Response not found during update: {response_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Response not found during update."
            )

        if update_result.modified_count == 0:
            logger.warning(f"Response {response_id} score/feedback was not modified by AI evaluation.")

        # Retrieve and validate updated response
        updated_response_doc = await db[settings.MONGODB_COLLECTION_RESPONSES].find_one({"_id": response_oid})
        if not updated_response_doc:
            logger.error(f"Failed to retrieve updated response {response_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated response after AI evaluation."
            )

        # Format response for output
        return InterviewResponseOut.model_validate(updated_response_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error evaluating response {response_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during AI evaluation."
        )


@router.get("/{interview_id}", response_model=InterviewOut, tags=["Details"])
async def get_interview_details(
    interview_id: str, current_user: User = Depends(get_current_active_user), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # (Code remains the same)
    logger.info(f"User {current_user.username} requesting details for interview {interview_id}")
    try:
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
        if not interview:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")
        candidate_id_str = str(interview.get("candidate_id"))
        # Permission check
        if current_user.role == "candidate" and str(current_user.id) != candidate_id_str: # Compare string IDs
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

        return InterviewOut.model_validate(interview)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching details for {interview_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve details.")

@router.get("/{interview_id}/responses", response_model=List[InterviewResponseOut], tags=["Details"])
async def get_interview_responses_list(
    interview_id: str, current_user: User = Depends(get_current_active_user), db: AsyncIOMotorClient = Depends(mongodb.get_db)
):
    # (Code remains the same)
    logger.info(f"User {current_user.username} requesting responses for interview {interview_id}")
    try:
        interview = await db[settings.MONGODB_COLLECTION_INTERVIEWS].find_one({"interview_id": interview_id})
        if not interview:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")
        candidate_id_str = str(interview.get("candidate_id"))
        # Permission check
        if current_user.role == "candidate" and str(current_user.id) != candidate_id_str: # Compare string IDs
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
        responses_cursor = db[settings.MONGODB_COLLECTION_RESPONSES].find({"interview_id": interview_id})
        responses = await responses_cursor.to_list(length=None)
        logger.info(f"Found {len(responses)} responses for interview {interview_id}")
        response_list = [InterviewResponseOut.model_validate(response) for response in responses]
        return response_list
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching responses for {interview_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve responses.")