from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr

UserRole = Literal["admin", "hr", "candidate"]

class User(BaseModel):
    username: str
    email: EmailStr
    hashed_password: str
    role: UserRole
    created_at: datetime = datetime.utcnow()

    class Config:
        json_schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "role": "candidate",
                "created_at": "2024-01-01T00:00:00"
            }
        } 