# LLM_interviewer/server/app/services/gemini_service.py

import google.generativeai as genai
import logging
import json
import re
# *** Ensure this import line includes Optional ***
from typing import List, Dict, Any, Optional, Tuple

# Import settings for API key
from app.core.config import settings

# Import schemas for type hinting return values (Ensure this path is correct)
try:
    # Assuming Question schema is in interview.py based on previous context
    from app.schemas.interview import Question
except ImportError:
    # Fallback or define a placeholder if schema isn't strictly needed for service logic
    Question = Dict[str, Any] # Use a dictionary as a fallback type hint

# Ensure logger is defined for this module
logger = logging.getLogger(__name__)

# --- Custom Exception Definition ---
class GeminiServiceError(Exception):
    """Custom exception for errors related to the Gemini Service."""
    def __init__(self, message="An error occurred in the Gemini service", status_code=500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = None

        # --- ADDED TEMPORARY DEBUG LOGGING ---
        if self.api_key:
            # Log only the first 5 and last 4 characters for security
            log_key_display = f"{self.api_key[:5]}...{self.api_key[-4:]}"
            logger.info(f"--- DEBUG: GeminiService attempting to configure with API Key: {log_key_display} ---")
        else:
            logger.info("--- DEBUG: GeminiService initialized with NO API Key from settings. ---")
        # --- END TEMPORARY DEBUG LOGGING ---

        if not self.api_key:
            logger.critical("CRITICAL: GEMINI_API_KEY is not set. GeminiService cannot be initialized.")
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME)
                logger.info(f"GeminiService initialized successfully with model: {settings.GEMINI_MODEL_NAME}")
            except Exception as e:
                logger.error(f"Failed to configure or initialize Gemini model: {e}", exc_info=True)
                self.model = None
                logger.critical("Gemini model initialization failed. Service methods requiring the model will not work.")

    def _check_model(self):
        """Internal helper to check if the model was initialized."""
        if self.model is None:
            logger.error("Gemini model is not available (check API key and initialization logs).")
            raise GeminiServiceError("Gemini model is not configured or initialization failed.", status_code=503)

    async def _call_gemini_api(self, prompt: str) -> Optional[str]:
        """Helper method to call the Gemini API and handle basic errors."""
        self._check_model()
        try:
            logger.debug(f"Sending prompt to Gemini (first 100 chars): {prompt[:100]}...")
            response = await self.model.generate_content_async(
                prompt,
                generation_config=settings.GEMINI_GENERATION_CONFIG,
                safety_settings=settings.GEMINI_SAFETY_SETTINGS
            )

            # Robust type checking and logging for the response object
            logger.debug(f"Gemini API raw response type: {type(response)}")
            if not hasattr(response, 'prompt_feedback') or not hasattr(response, 'text'):
                logger.error(f"Unexpected Gemini API response structure. Type: {type(response)}. Content (first 200 chars): {str(response)[:200]}")
                # If response is a string, this is a critical failure of the mock or an unexpected API behavior
                if isinstance(response, str):
                    # This directly addresses the issue where 'response' is a string when an object is expected.
                    raise GeminiServiceError(f"Gemini API returned a string unexpectedly, preventing access to attributes like 'prompt_feedback' or 'text'. Content (first 200 chars): {str(response)[:200]}", status_code=502)
                # For other unexpected structures that are not strings but lack necessary attributes
                # This logging will help diagnose if the mock is the problem or the actual API call is misbehaving.

            # --- DETAILED DEBUG LOGGING FOR RESPONSE OBJECT ---
            logger.debug(f"Gemini API raw response object type: {type(response)}")
            logger.debug(f"Gemini API raw response object dir: {dir(response)}")
            if hasattr(response, '__dict__'):
                logger.debug(f"Gemini API raw response object __dict__: {response.__dict__}")
            
            if hasattr(response, 'text'):
                logger.debug(f"Gemini API response HAS 'text' attribute. Value: {response.text[:100]}...")
            else:
                logger.debug("Gemini API response DOES NOT HAVE 'text' attribute.")

            if hasattr(response, 'prompt_feedback'):
                logger.debug(f"Gemini API response HAS 'prompt_feedback' attribute. Value: {response.prompt_feedback}")
                if response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason'):
                    logger.debug(f"Gemini API response prompt_feedback HAS 'block_reason'. Value: {response.prompt_feedback.block_reason}")
                elif response.prompt_feedback:
                    logger.debug("Gemini API response prompt_feedback DOES NOT HAVE 'block_reason'.")
            else:
                logger.debug("Gemini API response DOES NOT HAVE 'prompt_feedback' attribute.")
            # --- END DETAILED DEBUG LOGGING ---

            # Simplified check focusing on accessing text safely
            if hasattr(response, 'text') and response.text is not None: # Check if text is not None
                 logger.debug("Received response text from Gemini.")
                 return response.text
            # Check for prompt_feedback and block_reason *after* checking for text
            elif hasattr(response, 'prompt_feedback') and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                 block_reason = response.prompt_feedback.block_reason
                 logger.warning(f"Gemini request blocked. Reason: {block_reason}")
                 raise GeminiServiceError(f"Content generation blocked due to safety settings ({block_reason}).", status_code=400)
            else:
                 # If no text and no explicit block reason, it's an unexpected empty response
                 logger.warning(f"Gemini response received but contained no usable text content and no block reason. Response: {str(response)[:200]}")
                 raise GeminiServiceError("Gemini returned an unexpected empty or unusable response.", status_code=502)

        except GeminiServiceError: # Re-raise custom errors
            raise
        except Exception as e: # Catch other potential API errors
            logger.error(f"Error calling Gemini API: {e}", exc_info=True)
            # Include specific error details if available (e.g., from google.api_core.exceptions)
            error_detail = str(e)
            raise GeminiServiceError(f"Failed to get response from Gemini API: {error_detail}", status_code=502)


    def _clean_json_response(self, raw_text: Optional[str]) -> Optional[Any]:
        """Attempts to extract and parse JSON from the model's text response."""
        if not raw_text:
            logger.warning("Received empty text for JSON cleaning.")
            return None

        logger.debug("Attempting to clean and parse JSON response...")
        text_to_parse = raw_text.strip()
        # Regex to find JSON block within ```json ... ``` or ``` ... ```, or a plain JSON object/array
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```|({.*?}|\[.*?\])", text_to_parse, re.DOTALL)
        json_str_to_parse = None
        if match:
            # Prioritize content within backticks if both are found (group 1), else use plain object/array (group 2)
            json_str_to_parse = match.group(1) if match.group(1) else match.group(2)
        else:
            logger.debug("No clear JSON block/object/array found via regex, attempting to parse entire text.")
            json_str_to_parse = text_to_parse # Fallback to parsing the whole string

        if json_str_to_parse:
            json_str_to_parse = json_str_to_parse.strip()
            logger.debug(f"Attempting JSON parsing on: {json_str_to_parse[:200]}...")
            try:
                parsed_json = json.loads(json_str_to_parse)
                logger.debug("Successfully parsed JSON.")
                return parsed_json
            except json.JSONDecodeError as e:
                logger.error(f"JSONDecodeError parsing extracted string: {e}. String was: '{json_str_to_parse[:200]}...'")
                # Consider trying more aggressive cleaning here if needed
                return None
        else:
            logger.warning("Could not extract a potential JSON string to parse.")
            return None


    async def generate_questions(
        self,
        job_title: str,
        job_description: Optional[str], # Allow job_description to be optional
        num_questions: int = 5,
        category: str = "General",
        difficulty: str = "Medium",
        resume_text: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Generates interview questions. Returns list or raises GeminiServiceError.
        """
        prompt = f"""
        Generate {num_questions} interview questions suitable for a candidate applying for the role of '{job_title}'.
        """
        if job_description: # Only include if provided
             prompt += f"Job Description: {job_description}\n"
        prompt += f"Focus on the category: '{category}' and target difficulty: '{difficulty}'."

        if resume_text:
            prompt += f"\nConsider the candidate's resume for tailoring questions:\n--- RESUME ---\n{resume_text}\n--- END RESUME ---"

        prompt += f"""
        Return the questions strictly as a JSON list, where each object has keys: 'text' (string), 'category' (string, should be '{category}'), and 'difficulty' (string, should be '{difficulty}').
        Example format:
        [
          {{"text": "Can you describe your experience with...", "category": "{category}", "difficulty": "{difficulty}"}},
          {{"text": "How would you approach a situation where...", "category": "{category}", "difficulty": "{difficulty}"}}
        ]
        Ensure the output is ONLY the JSON list, without any introductory text or markdown formatting outside the JSON itself.
        """
        try:
            raw_response_text = await self._call_gemini_api(prompt)
            parsed_json = self._clean_json_response(raw_response_text)

            if isinstance(parsed_json, list):
                 logger.info(f"Successfully generated and parsed {len(parsed_json)} questions.")
                 # Optional: Validate structure of each dict in the list here
                 return parsed_json
            else:
                 logger.error(f"Parsed JSON response was not a list as expected. Type: {type(parsed_json)}. Raw Text: {raw_response_text[:200]}...")
                 raise GeminiServiceError("Failed to parse valid JSON list from Gemini response.")

        except GeminiServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during question generation: {e}", exc_info=True)
            raise GeminiServiceError(f"An unexpected error occurred: {e}")


    async def evaluate_answer(
        self,
        question_text: str,
        answer_text: str,
        job_title: Optional[str] = None,
        job_description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates an answer. Returns dict or raises ValueError/GeminiServiceError.
        """
        if not question_text or not answer_text:
             logger.warning("evaluate_answer called with missing question or answer text.")
             raise ValueError("Question text and answer text cannot be empty.")

        prompt = f"""
        Evaluate the following answer provided by a candidate for the interview question:
        Question: "{question_text}"
        Candidate's Answer: "{answer_text}"
        """
        if job_title:
            prompt += f"\nThe candidate is applying for the role of: '{job_title}'."
        if job_description:
            prompt += f"\nConsider the following job description context:\n{job_description}"

        prompt += """
        Provide an evaluation score between 0.0 and 5.0 (float, where 5.0 is excellent) and concise feedback (string).
        Return the evaluation strictly as a JSON object with keys: 'score' (float) and 'feedback' (string).
        Example format:
        {"score": 4.0, "feedback": "The candidate demonstrated strong understanding..."}
        Ensure the output is ONLY the JSON object, without any introductory text or markdown formatting.
        """
        try:
            raw_response_text = await self._call_gemini_api(prompt)
            parsed_json = self._clean_json_response(raw_response_text)

            if isinstance(parsed_json, dict) and 'score' in parsed_json and 'feedback' in parsed_json:
                 logger.info("Successfully evaluated answer and parsed response.")
                 # Optional: Validate score range/type and feedback type here
                 return parsed_json
            else:
                 logger.error(f"Parsed JSON response was not a valid evaluation dict. Content: {parsed_json}. Raw Text: {raw_response_text[:200]}...")
                 raise GeminiServiceError("Failed to parse valid evaluation JSON from Gemini response.")

        except GeminiServiceError:
             raise
        except ValueError: # Re-raise ValueError from input check
             raise
        except Exception as e:
             logger.error(f"Unexpected error during answer evaluation: {e}", exc_info=True)
             raise GeminiServiceError(f"An unexpected error occurred: {e}")

# Create a single instance for the application to use
gemini_service = GeminiService()
