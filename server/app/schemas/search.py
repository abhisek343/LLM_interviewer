# LLM_interviewer/server/app/schemas/search.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any, Dict

# Import HrProfileOut to extend it for ranked results
from .user import HrProfileOut, CandidateProfileOut # Added CandidateProfileOut

class RankedHR(HrProfileOut):
    """
    Represents an HR profile along with search relevance information.
    Inherits all fields from HrProfileOut.
    """
    relevance_score: Optional[float] = Field(
        None, 
        description="A score indicating the relevance of this HR profile to the search query.",
        example=0.85
    )
    match_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Details about what parts of the profile matched the search query (e.g., matched skills, experience).",
        example={"matched_skills": ["python", "fastapi"], "experience_match": True}
    )

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

# Schema for ranked candidate search results
class RankedCandidate(CandidateProfileOut):
    """
    Represents a Candidate profile along with search relevance information.
    Inherits all fields from CandidateProfileOut.
    """
    relevance_score: Optional[float] = Field(
        None,
        description="A score indicating the relevance of this candidate profile to the search query.",
        example=0.92
    )
    match_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Details about what parts of the profile matched the search query (e.g., matched skills, experience, keyword score).",
        example={"matched_skills": ["java", "spring"], "experience_match": True, "keyword_score": 0.5}
    )

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )
