from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class Subject(BaseModel):
    id: int
    name: str
    deadline: datetime
    materials: List[int] = []

class SubjectCreate(BaseModel):
    name: str
    deadline: datetime
    materials: List[int] = []

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    deadline: Optional[datetime] = None
    materials: Optional[List[int]] = None

subjectController = APIRouter(
    prefix="/v1/subject",
    tags=["Subjects"]
)

@subjectController.get("/list", response_model=List[Subject])
def list_subjects(group_id: int):
    return [
        {
            "id": 1,
            "name": "Mathematics",
            "deadline": datetime.now(),
            "materials": [101, 102]
        }
    ]

@subjectController.post("/create", response_model=Subject)
def create_subject(group_id: int, subject_in: SubjectCreate):
    return {
        "id": 99,
        "name": subject_in.name,
        "deadline": subject_in.deadline,
        "materials": subject_in.materials
    }

@subjectController.get("/{subject_id}", response_model=Subject)
def get_subject(group_id: int, subject_id: int):
    return {
        "id": subject_id,
        "name": "Physics",
        "deadline": datetime.now(),
        "materials": []
    }

@subjectController.patch("/{subject_id}", response_model=Subject)
def update_subject(group_id: int, subject_id: int, subject_update: SubjectUpdate):
    return {
        "id": subject_id,
        "name": subject_update.name or "Existing Subject",
        "deadline": subject_update.deadline or datetime.now(),
        "materials": subject_update.materials if subject_update.materials is not None else [1]
    }

@subjectController.delete("/{subject_id}")
def delete_subject(group_id: int, subject_id: int):
    return {
        "message": f"Subject {subject_id} for group {group_id} deleted successfully"
    }