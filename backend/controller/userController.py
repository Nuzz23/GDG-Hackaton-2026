from fastapi import APIRouter
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from service.userService import user_service, UserUpdate
from model.user import User

userController = APIRouter(
    prefix="/v1/user",
    tags=["Users"]
)

@userController.get("/profile")
def get_profile(user_id: int):
    return user_service.get_profile(user_id)

@userController.patch("/profile")
def update_profile(user_id: int, user_data: UserUpdate):
    return user_service.update_profile(user_id, user_data)

@userController.get("/groups")
def list_user_groups(user_id: int):
    return user_service.list_user_groups(user_id)

@userController.get("/subjects")
def list_user_subjects(user_id: int):
    return user_service.list_user_subjects(user_id)
