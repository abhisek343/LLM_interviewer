# LLM_interviewer/server/app/db/seed_data.py

import logging
from datetime import datetime, timezone
from pymongo import UpdateOne # Use UpdateOne for upserting
from typing import List, Dict, Any

# Import application components
from app.db.mongodb import mongodb # Import the singleton instance
from app.core.config import settings
from app.core.security import get_password_hash # For hashing admin password

logger = logging.getLogger(__name__)

# --- Default Questions Data ---
DEFAULT_QUESTIONS: List[Dict[str, Any]] = [
    {"question_id": "DEF001", "text": "Tell me about yourself.", "category": "Behavioral", "difficulty": "Easy"},
    {"question_id": "DEF002", "text": "What are your strengths and weaknesses?", "category": "Behavioral", "difficulty": "Easy"},
    {"question_id": "DEF003", "text": "Describe a challenging situation you faced at work and how you handled it.", "category": "Behavioral", "difficulty": "Medium"},
    {"question_id": "DEF004", "text": "Why are you interested in this role?", "category": "Motivation", "difficulty": "Easy"},
    {"question_id": "DEF005", "text": "Where do you see yourself in 5 years?", "category": "Career Goals", "difficulty": "Medium"},
    {"question_id": "DEF006", "text": "Why should we hire you?", "category": "Motivation", "difficulty": "Medium"},
    {"question_id": "DEF007", "text": "Do you have any questions for us?", "category": "Engagement", "difficulty": "Easy"},
]

async def _seed_default_questions_internal():
    """Internal function to seed default questions (idempotent)."""
    logger.info("Attempting to seed default questions...")
    try:
        db = mongodb.get_db()
        questions_collection = db[settings.MONGODB_COLLECTION_QUESTIONS]
        operations = []
        for q_data in DEFAULT_QUESTIONS:
            operations.append(
                UpdateOne(
                    {"question_id": q_data["question_id"]},
                    {
                        "$set": {
                           "text": q_data["text"],
                           "category": q_data["category"],
                           "difficulty": q_data["difficulty"],
                           "updated_at": datetime.now(timezone.utc)
                        },
                        "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
                    },
                    upsert=True
                )
            )
        if not operations:
            logger.info("No default questions defined.")
            return
        result = await questions_collection.bulk_write(operations, ordered=False)
        logger.info(f"Default questions seeding: Inserted={result.upserted_count}, Updated={result.matched_count}.")
    except Exception as e:
        logger.error(f"Error seeding default questions: {e}", exc_info=True)

async def _seed_admin_user_internal():
    """Internal function to seed the default admin user (idempotent)."""
    logger.info("Attempting to seed default admin user...")
    admin_email = settings.DEFAULT_ADMIN_EMAIL
    admin_pass = settings.DEFAULT_ADMIN_PASSWORD
    admin_username = settings.DEFAULT_ADMIN_USERNAME

    if not admin_email or not admin_pass or not admin_username:
        logger.warning("Default admin credentials (email, password, username) not fully set in settings. Skipping admin user seeding.")
        return

    try:
        db = mongodb.get_db()
        users_collection = db[settings.MONGODB_COLLECTION_USERS]

        # Check if admin user already exists
        existing_admin = await users_collection.find_one({"email": admin_email})
        if existing_admin:
            logger.info(f"Admin user with email '{admin_email}' already exists. Skipping creation.")
            return

        # Create admin user if not found
        admin_user_doc = {
            "username": admin_username,
            "email": admin_email,
            "hashed_password": get_password_hash(admin_pass),
            "role": "admin", # Explicitly set role
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "resume_path": None, # Default fields
            "resume_text": None,
        }
        result = await users_collection.insert_one(admin_user_doc)
        logger.info(f"Successfully inserted default admin user with ID: {result.inserted_id}")

    except Exception as e:
        logger.error(f"Error seeding admin user: {e}", exc_info=True)

# --- Main Seeding Function ---
async def seed_all_data():
    """Runs all seeding functions."""
    logger.info("Starting database seeding process...")
    await _seed_admin_user_internal()
    await _seed_default_questions_internal()
    logger.info("Database seeding process finished.")