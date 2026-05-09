from fastapi import APIRouter, Body
from pydantic import BaseModel, EmailStr
from typing import Optional, List

class User(BaseModel):
  id: int
  username: str
  email: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None

userController = APIRouter(
    prefix="/v1/user",
    tags=["Users"]
)

@userController.get("/profile", response_model=User)
def get_profile(user_id: int):
    return {
        "id": user_id,
        "username": "mario_rossi",
        "email": "mario@example.com",
    }

@userController.patch("/profile", response_model=User)
def update_profile(user_id: int, user_data: UserUpdate):
    return {
        "id": user_id,
        "username": user_data.username,
        "email": user_data.email
    }

@userController.get("/groups", response_model=List[str])
def list_user_groups(user_id: int):
    return ["admin", "editor"]

@userController.get("/subjects")
def list_user_subjects(user_id: int):
    return {
        "user_id": user_id,
        "subjects": ["Math", "Science"]
    }