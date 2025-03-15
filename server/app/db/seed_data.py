# LLM_interviewer/server/app/db/seed_data.py

import logging
from datetime import datetime, timezone
from pymongo import UpdateOne  # Use UpdateOne for upserting
from typing import List, Dict, Any

# Import application components
from app.db.mongodb import mongodb  # Import the singleton instance
from app.core.config import settings
from app.core.security import get_password_hash  # For hashing admin password

logger = logging.getLogger(__name__)

# --- Default Questions Data ---
DEFAULT_QUESTIONS: List[Dict[str, Any]] = [
    # Using custom question_id for idempotency
    {
        "question_id": "DEF001",
        "text": "Tell me about yourself.",
        "category": "Behavioral",
        "difficulty": "Easy",
    },
    {
        "question_id": "DEF002",
        "text": "What are your strengths and weaknesses?",
        "category": "Behavioral",
        "difficulty": "Easy",
    },
    {
        "question_id": "DEF003",
        "text": "Describe a challenging situation you faced at work and how you handled it.",
        "category": "Behavioral",
        "difficulty": "Medium",
    },
    {
        "question_id": "DEF004",
        "text": "Why are you interested in this role?",
        "category": "Motivation",
        "difficulty": "Easy",
    },
    {
        "question_id": "DEF005",
        "text": "Where do you see yourself in 5 years?",
        "category": "Career Goals",
        "difficulty": "Medium",
    },
    {
        "question_id": "DEF006",
        "text": "Why should we hire you?",
        "category": "Motivation",
        "difficulty": "Medium",
    },
    {
        "question_id": "DEF007",
        "text": "Do you have any questions for us?",
        "category": "Engagement",
        "difficulty": "Easy",
    },
]


async def _seed_default_questions_internal():
    """Internal function to seed default questions (idempotent)."""
    logger.info("Attempting to seed default questions...")
    try:
        db = mongodb.get_db()
        # Ensure collection name is fetched correctly from settings
        questions_collection_name = getattr(
            settings, "MONGODB_COLLECTION_QUESTIONS", "questions"
        )
        questions_collection = db[questions_collection_name]
        operations = []
        now = datetime.now(timezone.utc)
        for q_data in DEFAULT_QUESTIONS:
            # Check if essential fields are present in the question data
            if not all(
                k in q_data for k in ["question_id", "text", "category", "difficulty"]
            ):
                logger.warning(f"Skipping invalid default question data: {q_data}")
                continue

            operations.append(
                UpdateOne(
                    {"question_id": q_data["question_id"]},  # Use custom ID as filter
                    {
                        "$set": {  # Fields to set on match or insert
                            "text": q_data["text"],
                            "category": q_data["category"],
                            "difficulty": q_data["difficulty"],
                            "updated_at": now,
                        },
                        "$setOnInsert": {  # Fields to set only on insert
                            "question_id": q_data[
                                "question_id"
                            ],  # Ensure ID is set on insert
                            "created_at": now,
                        },
                    },
                    upsert=True,
                )
            )
        if not operations:
            logger.info("No valid default questions defined to seed.")
            return

        result = await questions_collection.bulk_write(operations, ordered=False)
        logger.info(
            f"Default questions seeding: Upserted={result.upserted_count}, Matched/Modified={result.modified_count}."
        )  # Log modified count too
    except AttributeError as e:
        logger.error(
            f"Database/Collection setting missing in config for questions seeding: {e}"
        )
    except Exception as e:
        logger.error(f"Error seeding default questions: {e}", exc_info=True)


async def _seed_admin_user_internal():
    """Internal function to seed the default admin user (idempotent)."""
    logger.info("Attempting to seed default admin user...")
    admin_email = settings.DEFAULT_ADMIN_EMAIL
    admin_pass = settings.DEFAULT_ADMIN_PASSWORD
    admin_username = settings.DEFAULT_ADMIN_USERNAME

    if not admin_email or not admin_pass or not admin_username:
        logger.warning(
            "Default admin credentials not fully set. Skipping admin user seeding."
        )
        return

    try:
        db = mongodb.get_db()
        users_collection_name = getattr(settings, "MONGODB_COLLECTION_USERS", "users")
        users_collection = db[users_collection_name]

        # Check if admin user already exists by email
        existing_admin = await users_collection.find_one({"email": admin_email})
        if existing_admin:
            logger.info(
                f"Admin user '{admin_email}' already exists. Skipping creation."
            )
            return

        # Check if username is taken by someone else (optional safety check)
        existing_username = await users_collection.find_one(
            {"username": admin_username}
        )
        if existing_username:
            logger.error(
                f"Cannot seed default admin: Username '{admin_username}' is already taken by another user ({existing_username['email']})."
            )
            return

        # Create admin user document, ensuring all fields from User model are present
        now = datetime.now(timezone.utc)
        admin_user_doc = {
            "username": admin_username,
            "email": admin_email,
            "hashed_password": get_password_hash(admin_pass),
            "role": "admin",
            "created_at": now,
            "updated_at": now,
            # Explicitly set optional fields added to User model to None for consistency
            "resume_path": None,
            "resume_text": None,
            "mapping_status": None,  # Not applicable to admin
            "assigned_hr_id": None,  # Not applicable to admin
            "hr_status": None,  # Not applicable to admin
            "admin_manager_id": None,  # Not applicable to admin
            "years_of_experience": None,  # Not applicable to admin
        }
        result = await users_collection.insert_one(admin_user_doc)
        logger.info(
            f"Successfully inserted default admin user '{admin_email}' with ID: {result.inserted_id}"
        )

    except AttributeError as e:
        logger.error(
            f"Database/Collection setting missing in config for admin seeding: {e}"
        )
    except Exception as e:
        logger.error(f"Error seeding admin user: {e}", exc_info=True)


# --- Main Seeding Function ---
async def seed_all_data():
    """Runs all seeding functions during application startup."""
    logger.info("Starting database seeding process...")
    # Seed admin first (in case questions somehow depended on it, though unlikely)
    await _seed_admin_user_internal()
    # Then seed questions
    await _seed_default_questions_internal()
    logger.info("Database seeding process finished.")
