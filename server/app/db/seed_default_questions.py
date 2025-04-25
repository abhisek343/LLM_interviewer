 # LLM_interviewer/server/app/db/seed_default_questions.py

import logging
from datetime import datetime
from app.db.mongodb import mongodb
from app.core.config import settings # Import settings to get collection name

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define default questions
# Adjust these questions based on general technical roles
DEFAULT_QUESTIONS = [
    {
        "text": "Can you explain the difference between SQL and NoSQL databases? Provide an example scenario where each might be preferred.",
        "category": "Databases",
        "difficulty": "Medium",
    },
    {
        "text": "What is RESTful API design? Describe the key principles.",
        "category": "API Design",
        "difficulty": "Medium",
    },
    {
        "text": "Describe the concept of asynchronous programming. Why is it important in web development?",
        "category": "Programming Concepts",
        "difficulty": "Medium",
    },
    {
        "text": "What is version control (like Git)? Why is it essential for software development teams?",
        "category": "Development Practices",
        "difficulty": "Easy",
    },
    {
        "text": "Explain the basic principles of Object-Oriented Programming (OOP).",
        "category": "Programming Concepts",
        "difficulty": "Easy",
    },
    {
        "text": "What is Test-Driven Development (TDD)?",
        "category": "Testing",
        "difficulty": "Medium",
    },
    {
        "text": "Describe a challenging technical problem you faced on a previous project and how you solved it.",
        "category": "Behavioral/Problem Solving",
        "difficulty": "Medium",
    },
]

async def seed_default_questions():
    """
    Seeds the database with default interview questions if the collection is empty.
    """
    try:
        db = mongodb.get_db()
        questions_collection = db[settings.MONGODB_COLLECTION_QUESTIONS] # Use collection name from settings

        # Check if the collection already has documents
        count = await questions_collection.count_documents({})
        if count > 0:
            logger.info(f"'{settings.MONGODB_COLLECTION_QUESTIONS}' collection already contains documents ({count}). Skipping default question seeding.")
            return

        logger.info(f"'{settings.MONGODB_COLLECTION_QUESTIONS}' collection is empty. Seeding {len(DEFAULT_QUESTIONS)} default questions...")

        # Add creation timestamp to each question
        questions_to_insert = []
        for q in DEFAULT_QUESTIONS:
            q_doc = q.copy() # Create a copy to avoid modifying the original list
            q_doc["created_at"] = datetime.utcnow()
            # You could add a unique identifier here if needed,
            # but MongoDB's _id will be generated automatically.
            questions_to_insert.append(q_doc)

        # Insert the questions into the database
        if questions_to_insert:
            insert_result = await questions_collection.insert_many(questions_to_insert)
            logger.info(f"Successfully inserted {len(insert_result.inserted_ids)} default questions.")
        else:
            logger.warning("No default questions were defined to insert.")

    except AttributeError:
        logger.error("MONGODB_COLLECTION_QUESTIONS setting not found in config. Cannot seed questions.")
    except Exception as e:
        logger.error(f"Error seeding default questions: {e}", exc_info=True)
        # Depending on requirements, you might want to raise this error
        # raise

# Note: This function needs to be called during application startup.
# Ensure it's uncommented and called in `app/main.py`'s `startup_db_client` function.
# Example in main.py startup:
# from .db.seed_default_questions import seed_default_questions
# await seed_default_questions()