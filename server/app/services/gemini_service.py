import google.generativeai as genai
from app.core.config import get_settings
from typing import List, Dict
import json

settings = get_settings()
genai.configure(api_key=settings.GEMINI_API_KEY)

class GeminiService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-pro')
        
    async def generate_questions(
        self,
        role: str,
        tech_stack: List[str],
        num_questions: int = 5
    ) -> List[Dict]:
        try:
            prompt = f"""
            Generate {num_questions} technical interview questions for a {role} position.
            Focus on these technologies: {', '.join(tech_stack)}.
            
            For each question, provide:
            1. The question text
            2. Category (e.g., "Frontend", "Backend", "System Design")
            3. Difficulty level ("Easy", "Medium", "Hard")
            
            Format the response as a JSON array of objects with these fields:
            - text: string
            - category: string
            - difficulty: string
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse the response
            try:
                questions = json.loads(response.text)
                return questions
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract questions from text
                questions = []
                lines = response.text.split('\n')
                for line in lines:
                    if line.strip() and not line.startswith(('1.', '2.', '3.', '4.', '5.')):
                        questions.append({
                            "text": line.strip(),
                            "category": "Technical",
                            "difficulty": "Medium"
                        })
                return questions[:num_questions]
                
        except Exception as e:
            print(f"Error generating questions with Gemini: {str(e)}")
            return []

gemini_service = GeminiService() 