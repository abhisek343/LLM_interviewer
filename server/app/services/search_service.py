# LLM_interviewer/server/app/services/search_service.py

import logging
from typing import List, Dict, Optional, Any, Literal
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException, status

from app.db.mongodb import mongodb
from app.core.config import settings
from app.models.user import User, CandidateMappingStatus, HrStatus

# ResumeAnalyzerService might not be directly needed if data is stored,
# but keep import for potential future re-analysis features.
from .resume_analyzer_service import ResumeAnalyzerService

# Import centralized search schemas
from app.schemas.search import RankedHR, RankedCandidate # Import both
# For RankedCandidate, CandidateProfileOut is already a base for it in schemas.search
# from app.schemas.user import CandidateProfileOut # No longer needed here directly for RankedCandidate

logger = logging.getLogger(__name__)

# InternalRankedCandidate is no longer needed as we will use RankedCandidate from app.schemas.search

class SearchService:
    """
    Service for searching and ranking Users (Candidates, HRs).
    Assumes resume analysis results (skills, YoE) are stored on the User document
    (e.g., as 'extracted_skills_list' and 'estimated_yoe').
    Requires a text index on 'resume_text' for keyword search.
    """

    def __init__(self, db: Optional[AsyncIOMotorClient] = None):
        self.db = db if db is not None else mongodb.get_db()
        if self.db is None:
            raise RuntimeError("Database not available in SearchService.")
        self.user_collection = self.db[settings.MONGODB_COLLECTION_USERS]
        # Analyzer instance isn't strictly needed here if we assume data is pre-stored
        # self.analyzer = analyzer if analyzer else resume_analyzer_service

    def _get_stored_analysis_data(self, user_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to safely get pre-stored analysis data from user document."""
        # Adjust field names to match EXACTLY how they are stored in MongoDB
        # These names MUST match the keys used in the update_doc within the
        # upload_resume functions in candidates.py and hr.py routes.
        return {
            "extracted_skills": user_doc.get(
                "extracted_skills_list", []
            ),  # Assumed stored field name
            "estimated_experience_years": user_doc.get("estimated_yoe", 0.0)
            or 0.0,  # Assumed stored field name
        }

    def _calculate_tech_match(
        self, candidate_skills: List[str], required_skills: List[str]
    ) -> float:
        """Calculates Jaccard Index for skill matching."""
        if not required_skills:
            return 1.0  # No required skills means perfect match? Or 0.0? Define requirement. Assume 1.0 for now.
        if not candidate_skills:
            return 0.0

        # Ensure comparison is case-insensitive and ignores leading/trailing spaces
        set_candidate = set(s.lower().strip() for s in candidate_skills if s)
        set_required = set(s.lower().strip() for s in required_skills if s)

        intersection = len(set_candidate.intersection(set_required))
        union = len(set_candidate.union(set_required))
        return float(intersection / union) if union > 0 else 0.0

    def _calculate_ranking_score(
        self,
        user_doc: Dict[str, Any],  # Raw doc from DB
        extracted_data: Dict[str, Any],  # Data from _get_stored_analysis_data
        search_skills: Optional[List[str]] = None,
        mongo_text_score: float = 0.0,
    ) -> float:
        """Calculates ranking score: (WEIGHT_TECH * tech_match) * YoE_Multiplier + (WEIGHT_MONGO * mongo_text_score)"""
        # --- Constants for Weighting (Tune these values) ---
        WEIGHT_TECH = 0.70  # Weight for skill match component
        WEIGHT_MONGO = 0.30  # Weight for MongoDB text search relevance score
        # ---

        extracted_skills = extracted_data.get("extracted_skills", [])
        yoe = extracted_data.get("estimated_experience_years", 0.0)

        # Calculate Tech Match Score
        tech_match_score = 1.0  # Default if no skills specified in search
        if search_skills:
            # Use the internal helper method
            tech_match_score = self._calculate_tech_match(
                extracted_skills, search_skills
            )

        # Calculate Experience Multiplier (YoE=0 treated as 1x multiplier)
        experience_multiplier = max(1.0, yoe)

        # Calculate base score from tech match and experience
        base_score = tech_match_score * experience_multiplier

        # Combine with MongoDB text score (if available) using weights
        combined_score = (WEIGHT_TECH * base_score) + (WEIGHT_MONGO * mongo_text_score)

        return round(combined_score, 4)

    async def search_candidates(
        self,
        keyword: Optional[str] = None,
        required_skills: Optional[List[str]] = None,
        yoe_min: Optional[int] = None,
        limit: int = 20,
    ) -> List[RankedCandidate]: # Use RankedCandidate from app.schemas.search
        """Searches and ranks candidates (status 'pending_assignment')."""
        logger.info(
            f"Searching candidates. Keywords: {keyword}, Skills: {required_skills}, YoE Min: {yoe_min}"
        )

        # --- 1. Build Query ---
        query: Dict[str, Any] = {
            "role": "candidate",
            "mapping_status": "pending_assignment",
            # Ensure required fields for ranking exist (assuming they are stored)
            "estimated_yoe": {"$exists": True},  # Assumes 'estimated_yoe' field exists
            "extracted_skills_list": {
                "$exists": True
            },  # Assumes 'extracted_skills_list' field exists
            "resume_text": {"$ne": None},
        }
        projection: Optional[Dict[str, Any]] = None  # Initialize projection
        sort_criteria: List[Tuple[str, Any]] = [("updated_at", -1)]  # Default sort

        # Add keyword text search filter and projection/sort
        if keyword:
            query["$text"] = {"$search": keyword}
            projection = {
                "mongo_score": {"$meta": "textScore"}
            }  # Project score as 'mongo_score'
            sort_criteria = [
                ("mongo_score", {"$meta": "textScore"})
            ]  # Sort by relevance first
            logger.debug("Added $text search to candidate query")

        # Add YoE filter (uses stored 'estimated_yoe' field)
        if yoe_min is not None:
            # Ensure query uses $and if keyword search is also present
            if "$text" in query:
                query = {"$and": [query, {"estimated_yoe": {"$gte": float(yoe_min)}}]}
            else:
                query["estimated_yoe"] = {"$gte": float(yoe_min)}
            logger.debug(f"Added candidate YoE filter: >= {yoe_min}")

        # Add skill filter (uses stored 'extracted_skills_list', assumes lowercase list)
        if required_skills:
            skills_lower = [skill.lower().strip() for skill in required_skills]
            # Use $in to fetch candidates who have at least one of the required skills
            # The ranking logic will then score based on the proportion of all required skills matched
            skill_filter = {"extracted_skills_list": {"$in": skills_lower}}
            if "$and" in query:
                query["$and"].append(skill_filter)
            elif "$text" in query:  # Need $and if text search and skills are present
                query = {"$and": [query, skill_filter]}
            else:
                # If only skill filter is present, add it directly
                query["extracted_skills_list"] = {"$in": skills_lower}
            logger.debug(f"Added candidate skill filter (in): {skills_lower}")

        # --- 2. Fetch Candidates ---
        try:
            # Fetch slightly more to allow for reranking after score calculation
            # Apply projection if defined
            find_query = self.user_collection.find(
                query, projection=projection if projection else None
            )
            cursor = find_query.sort(sort_criteria).limit(limit * 3)
            candidates_to_rank = await cursor.to_list(length=None)
            logger.debug(
                f"Found {len(candidates_to_rank)} candidates matching query for ranking."
            )
        except Exception as e:
            logger.error(
                f"Database query failed during candidate search: {e}", exc_info=True
            )
            # Check for specific PyMongo OperationFailure due to missing text index
            if isinstance(e, Exception) and "text index required" in str(e).lower(): # Check type more broadly
                logger.warning(
                    "Text search failed due to missing 'resume_text' index. Returning empty results for keyword search part."
                )
                # If it's a text index issue, we might want to return empty or proceed without text score
                # For now, let's return empty if a keyword was provided, as text search is key.
                if keyword: # Only return empty if keyword search was the primary goal
                    return []
                # If no keyword, but other filters, the error might be different or we might proceed.
                # This specific handling is for when $text fails.
            
            # Fallback for other DB errors
            raise HTTPException(
                status_code=500, detail="Database error during candidate search."
            )

        if not candidates_to_rank:
            return []

        # --- 3. Rank Candidates ---
        ranked_list = []
        for cand_doc in candidates_to_rank:
            extracted_data = self._get_stored_analysis_data(
                cand_doc
            )  # Use internal helper
            mongo_score = cand_doc.get(
                "mongo_score", 0.0
            )  # Get projected score if keyword search used

            # Calculate the final combined score
            final_score = self._calculate_ranking_score(  # Use internal helper
                cand_doc,
                extracted_data,
                search_skills=required_skills,
                mongo_text_score=mongo_score,
            )

            try:
                # Populate response model using app.schemas.search.RankedCandidate
                # This schema expects 'relevance_score' and 'match_details'
                # It inherits fields from CandidateProfileOut.
                
                # Data for CandidateProfileOut part (most fields are in cand_doc)
                # Ensure all fields required by CandidateProfileOut are correctly mapped
                candidate_profile_data = {
                    **cand_doc, 
                    "id": str(cand_doc["_id"]),
                    "extracted_skills_list": extracted_data.get("extracted_skills", []),
                    "estimated_yoe": extracted_data.get("estimated_experience_years"),
                }

                # Data for RankedCandidate specific fields
                ranked_candidate_specific_data = {
                    "relevance_score": final_score,
                    "match_details": { # Example match_details
                        "mongo_text_score": mongo_score,
                        "calculated_score_components": "details_can_be_added_here"
                    }
                }
                
                final_candidate_data = {**candidate_profile_data, **ranked_candidate_specific_data}
                
                ranked_entry = RankedCandidate.model_validate(final_candidate_data)
                ranked_list.append(ranked_entry)
            except Exception as e:
                logger.error(
                    f"Pydantic validation failed for candidate {cand_doc.get('_id')}: {e}",
                    exc_info=True,
                )

        # --- 4. Sort by final calculated score and Limit ---
        ranked_list.sort(key=lambda x: x.relevance_score if x.relevance_score is not None else 0, reverse=True)
        return ranked_list[:limit]

    async def search_hr_profiles(
        self,
        keyword: Optional[str] = None,
        yoe_min: Optional[int] = None,
        status_filter: Optional[HrStatus] = "profile_complete", # type: ignore
        limit: int = 20,
    ) -> List[RankedHR]: # Uses RankedHR from app.schemas.search
        """Searches HR profiles. Basic filtering, simple ranking for now."""
        logger.info(
            f"Searching HR profiles. Status: {status_filter}, Keyword: {keyword}, YoE Min: {yoe_min}"
        )

        # --- 1. Build Query ---
        query: Dict[str, Any] = {"role": "hr"}
        if status_filter:
            query["hr_status"] = status_filter

        # Filter by HR's specific YoE field
        if yoe_min is not None:
            query["years_of_experience"] = {"$gte": yoe_min}

        # Keyword search on HR resume (Requires text index)
        projection = None
        sort_criteria: List[Tuple[str, Any]] = [("updated_at", -1)]
        if keyword:
            query["resume_text"] = {"$ne": None}  # Only search HRs with resumes
            query["$text"] = {"$search": keyword}
            projection = {"mongo_score": {"$meta": "textScore"}}
            sort_criteria = [("mongo_score", {"$meta": "textScore"})]
            logger.debug("Added $text search to HR query")

        # --- 2. Fetch HRs ---
        try:
            find_query = self.user_collection.find(
                query, projection=projection if projection else None
            )
            cursor = find_query.sort(sort_criteria).limit(
                limit
            )  # Limit directly as ranking is simple
            hr_list_docs = await cursor.to_list(length=None)
            logger.debug(f"Found {len(hr_list_docs)} HRs matching query.")
        except Exception as e:
            logger.error(f"Database query failed during HR search: {e}", exc_info=True)
            if isinstance(e, Exception) and "text index required" in str(e).lower():
                logger.warning(
                    "Text search failed for HR profiles due to missing 'resume_text' index. Returning empty results for keyword search part."
                )
                if keyword: # Only return empty if keyword search was the primary goal
                    return []
            
            raise HTTPException(
                status_code=500, detail="Database error during HR search."
            )

        if not hr_list_docs:
            return []

        # --- 3. Format Results (Using text score as primary score for now) ---
        results = []
        for hr_doc in hr_list_docs:
            try:
                extracted_data = self._get_stored_analysis_data(hr_doc)
                mongo_score = hr_doc.get(
                    "mongo_score", 0.0
                )  # Get text score if available

                # Populate response model using app.schemas.search.RankedHR
                # This schema expects 'relevance_score' and 'match_details'
                # It inherits fields from HrProfileOut.
                
                # Data for HrProfileOut part
                hr_profile_data = {**hr_doc, "id": str(hr_doc["_id"])}
                
                # Data for RankedHR specific fields
                # For now, using mongo_score as relevance_score, no complex match_details
                ranked_hr_specific_data = {
                    "relevance_score": round(mongo_score, 4),
                    "match_details": {"text_search_score": round(mongo_score, 4)} # Example detail
                }
                
                # Combine data for RankedHR validation
                # Ensure all fields from HrProfileOut are present in hr_profile_data
                # or handled by Pydantic's validation (e.g. default values)
                final_hr_data = {**hr_profile_data, **ranked_hr_specific_data}

                # Ensure all fields required by HrProfileOut are correctly mapped from hr_doc
                # Example: HrProfileOut expects 'years_of_experience', ensure hr_doc has it or it's optional
                # The HrProfileOut schema has 'years_of_experience: Optional[int] = Field(None, ge=0)'
                # It also has 'extracted_skills_list' (from UserOut via HrProfileOut)
                # and 'resume_path' (from UserOut)
                # The internal RankedHR had 'extracted_skills' aliased to 'extracted_skills_list'
                # Let's ensure this alignment for the external schema.
                # HrProfileOut inherits 'resume_path' from UserOut.
                # It also has 'company: Optional[str] = None'.
                # The User model should have these fields for HR users.

                # Map fields from hr_doc to what RankedHR (from app.schemas.search) expects
                # This includes fields from HrProfileOut (which comes from UserOut)
                mapped_data = {
                    "id": str(hr_doc["_id"]),
                    "username": hr_doc.get("username"),
                    "email": hr_doc.get("email"),
                    "role": hr_doc.get("role"), # Should be "hr"
                    "created_at": hr_doc.get("created_at"),
                    "resume_path": hr_doc.get("resume_path"),
                    # HrProfileOut specific fields
                    "hr_status": hr_doc.get("hr_status"), # Added hr_status
                    "years_of_experience": hr_doc.get("years_of_experience"),
                    "company": hr_doc.get("company"),
                    "admin_manager_id": hr_doc.get("admin_manager_id"), # Added admin_manager_id
                    # UserOut fields (already covered by HrProfileOut inheritance)
                    # CandidateProfileOut specific fields are not relevant here
                    # RankedHR specific fields
                    "relevance_score": round(mongo_score, 4),
                    "match_details": {"text_search_score": round(mongo_score, 4)}, # Example
                    # Ensure extracted_skills_list is populated if present in HrProfileOut
                    "extracted_skills_list": extracted_data.get("extracted_skills", [])
                }
                # Filter out None values if Pydantic models don't handle them as default
                # mapped_data = {k: v for k, v in mapped_data.items() if v is not None}


                ranked_entry = RankedHR.model_validate(mapped_data)
                results.append(ranked_entry)
            except Exception as e:
                logger.error(
                    f"Pydantic validation failed for HR profile {hr_doc.get('_id')}: {e}",
                    exc_info=True,
                )

        # Re-sort by relevance_score
        results.sort(key=lambda x: x.relevance_score if x.relevance_score is not None else 0, reverse=True)

        return results
