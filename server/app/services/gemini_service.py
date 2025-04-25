# LLM_interviewer/server/app/services/gemini_service.py

import google.generativeai as genai
from app.core.config import get_settings
from typing import List, Dict, Optional, Any
import json
import logging
import re
from datetime import datetime
from uuid import uuid4

settings = get_settings()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Gemini API Configuration ---
if not settings.GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not found in settings. GeminiService will not function.")
else:
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to configure Google AI client: {e}", exc_info=True)

class GeminiService:
    def __init__(self):
        self.model_name = 'gemini-pro'
        self.model = None
        try:
            if not settings.GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY not found. GeminiService will not function.")
                return
                
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"GeminiService initialized with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize GenerativeModel '{self.model_name}': {e}", exc_info=True)
            self.model = None

    async def generate_questions(
        self,
        role: str,
        tech_stack: List[str],
        num_questions: int = 5,
        resume_text: Optional[str] = None
    ) -> List[Dict]:
        """Generates interview questions, optionally using resume context."""
        if not self.model:
            logger.error("Cannot generate questions: Gemini model not initialized.")
            return []
        try:
            prompt_lines = [
                f"Generate {num_questions} technical interview questions suitable for a candidate applying for a '{role}' position.",
                f"The key technologies for this role are: {', '.join(tech_stack)}."
            ]
            if resume_text and resume_text.strip():
                logger.info(f"Including resume context in prompt for role '{role}'.")
                prompt_lines.extend([
                    "\nConsider the following candidate resume information when tailoring the questions:",
                    "--- Resume Start ---",
                    resume_text.strip(),
                    "--- Resume End ---\n",
                    "Tailor the questions based on the candidate's experience and skills mentioned in the resume, while still covering the key technologies."
                ])
            else:
                logger.info(f"No resume context provided for prompt for role '{role}'.")

            prompt_lines.extend([
                "\nFor each question, please provide:",
                "1. The question text.",
                "2. A relevant category (e.g., 'Python', 'React', 'System Design', 'Behavioral', 'Databases').",
                "3. A difficulty level ('Easy', 'Medium', 'Hard').",
                "\nFormat the entire response strictly as a JSON array of objects. Each object must have exactly these keys: 'text', 'category', 'difficulty'.",
                "Example format: [{'text': '...', 'category': '...', 'difficulty': '...'}, ...]"
            ])
            final_prompt = "\n".join(prompt_lines)
            logger.debug(f"Gemini Prompt:\n{final_prompt}")

            response = await self.model.generate_content_async(
                final_prompt,
                request_options={"timeout": 90}
            )
            logger.debug(f"Gemini Raw Response (Questions): {response}")
            if not response or not hasattr(response, 'text') or not response.text:
                logger.warning("Gemini API (Questions) returned an empty or invalid response.")
                return []

            try:
                cleaned_text = self._clean_json_response(response.text)
                questions = json.loads(cleaned_text)
                if not isinstance(questions, list):
                    logger.warning(f"Gemini API response (Questions) parsed but is not a list. Parsed data: {questions}")
                    return []
                
                # Add required fields for QuestionOut schema
                validated_questions = []
                for q in questions:
                    if isinstance(q, dict) and all(k in q for k in ['text', 'category', 'difficulty']):
                        q['question_id'] = str(uuid4())
                        q['created_at'] = datetime.utcnow().isoformat()
                        validated_questions.append(q)
                
                if not validated_questions:
                    logger.warning(f"Gemini API response (Questions) parsed as list, but no valid question objects found. Response text: {response.text}")
                    return []
                
                logger.info(f"Successfully parsed {len(validated_questions)} questions from Gemini response.")
                return validated_questions[:num_questions]
            except json.JSONDecodeError as json_err:
                logger.warning(f"Gemini API response (Questions) could not be parsed as JSON. Error: {json_err}. Response text: {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error generating questions with Gemini: {e}", exc_info=True)
            return []

    async def evaluate_answer(
        self,
        question_text: str,
        answer_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates a candidate's answer to a specific question using the Gemini API.
        """
        if not self.model:
            logger.error("Cannot evaluate answer: Gemini model not initialized.")
            return None

        if not question_text or not answer_text:
            logger.warning("Cannot evaluate answer: Missing question or answer text.")
            raise ValueError("Question and answer text cannot be empty")

        try:
            prompt = f"""
            Act as an expert technical interviewer evaluating a candidate's response.
            Evaluate the following answer based *only* on the provided question and answer text.
            Consider correctness, completeness, clarity, and relevance to the question.

            **Question:**
            {question_text}

            **Candidate's Answer:**
            {answer_text}

            **Evaluation Task:**
            1. Provide a numerical score between 0.0 and 5.0 (inclusive), where 0 indicates completely incorrect/irrelevant and 5 indicates a perfect answer. Use decimal points if appropriate (e.g., 3.5).
            2. Provide brief, constructive feedback (1-3 sentences) explaining the reasoning for the score. Focus on strengths and areas for improvement based *solely* on the given answer's content in relation to the question. Do not add information not present in the answer.

            **Output Format:**
            Return your evaluation strictly as a JSON object with exactly two keys:
            - "score": float (numerical score between 0.0 and 5.0)
            - "feedback": string (brief textual feedback)

            Example JSON output: {{"score": 4.0, "feedback": "Correctly identifies the main concept but lacks detail on edge cases."}}
            """
            logger.debug(f"Gemini Evaluation Prompt:\n{prompt}")

            response = await self.model.generate_content_async(
                prompt,
                request_options={"timeout": 60}
            )
            logger.debug(f"Gemini Raw Response (Evaluation): {response}")

            if not response or not hasattr(response, 'text') or not response.text:
                logger.warning("Gemini API (Evaluation) returned an empty or invalid response object or text.")
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    logger.warning(f"Gemini prompt feedback: {response.prompt_feedback}")
                return None

            try:
                cleaned_text = self._clean_json_response(response.text)
                evaluation = json.loads(cleaned_text)

                if not isinstance(evaluation, dict) or 'score' not in evaluation or 'feedback' not in evaluation:
                    logger.warning(f"Gemini API response (Evaluation) parsed but not in expected dict format with 'score' and 'feedback'. Parsed: {evaluation}")
                    return None

                score = evaluation.get('score')
                feedback = evaluation.get('feedback', '')

                if not isinstance(score, (int, float)) or not 0.0 <= score <= 5.0:
                    logger.warning(f"Invalid score in evaluation: {score}")
                    return None

                logger.info(f"Successfully evaluated answer. Score: {score}, Feedback: {feedback[:100]}...")
                return {"score": float(score), "feedback": feedback.strip()}

            except json.JSONDecodeError as json_err:
                logger.warning(f"Gemini API response (Evaluation) could not be parsed as JSON. Error: {json_err}. Response text: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error evaluating answer with Gemini: {e}", exc_info=True)
            return None

    def _clean_json_response(self, text: str) -> str:
        """Removes potential markdown fences and leading/trailing whitespace."""
        # Remove triple backticks and optional 'json' language identifier
        cleaned = re.sub(r"^\s*```(json)?\s*", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
        # Remove any text before or after the JSON
        cleaned = re.sub(r"^.*?(\{.*\}).*$", r"\1", cleaned, flags=re.DOTALL)
        # Strip leading/trailing whitespace
        return cleaned.strip()

# Instantiate the service
gemini_service = GeminiService()