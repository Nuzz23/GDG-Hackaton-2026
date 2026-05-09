from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class Group(BaseModel):
    id: int
    name: str
    creationDate: datetime
    users: List[int] = []

class GroupCreate(BaseModel):
    name: str
    users: List[int] = []

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    users: Optional[List[int]] = None

class GroupUserAdd(BaseModel):
    group_id: int
    user_id: int

groupController = APIRouter(
    prefix="/v1/group",
    tags=["Groups"]
)

@groupController.get("/list", response_model=List[Group])
def list_groups():
    return [
        {
            "id": 1,
            "name": "Study Group A",
            "creationDate": datetime.now(),
            "users": [1, 2, 3]
        }
    ]

@groupController.get("/{group_id}/members", response_model=List[int])
def list_group_members(group_id: int):
    return [1, 2, 3]

@groupController.get("/{group_id}/subjects", response_model=List[str])
def list_group_subjects(group_id: int):
    return ["Math", "History"]

@groupController.post("/create", response_model=Group)
def create_group(group_in: GroupCreate):
    return {
        "id": 10,
        "name": group_in.name,
        "creationDate": datetime.now(),
        "users": group_in.users
    }

@groupController.post("/add")
def add_to_group(payload: GroupUserAdd):
    return {
        "message": f"User {payload.user_id} added to group {payload.group_id} successfully"
    }

@groupController.get("/{group_id}", response_model=Group)
def get_group(group_id: int):
    return {
        "id": group_id,
        "name": "Specific Group",
        "creationDate": datetime.now(),
        "users": [1, 2]
    }

@groupController.patch("/{group_id}", response_model=Group)
def update_group(group_id: int, group_update: GroupUpdate):
    return {
        "id": group_id,
        "name": group_update.name or "Updated Name",
        "creationDate": datetime.now(),
        "users": group_update.users if group_update.users is not None else []
    }

@groupController.delete("/{group_id}")
def delete_group(group_id: int):
    return {
        "message": f"Group {group_id} deleted successfully"
    }