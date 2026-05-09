from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from model.subject import Subject
from repository.subjectRepository import SubjectRepository

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

class SubjectService:
    """Service layer for subject operations"""

    def __init__(self):
        self.repository = SubjectRepository()

    def list_subjects(self, group_id: int) -> List[Subject]:
        """Get list of subjects for a group"""
        # TODO: Implement database query
        return [
            Subject(
                id=1,
                name="Mathematics",
                deadline=datetime.now(),
                materials=[101, 102]
            )
        ]

    def get_subject(self, group_id: int, subject_id: int) -> Subject:
        """Get a specific subject by ID"""
        # TODO: Implement database query
        return Subject(
            id=subject_id,
            name="Physics",
            deadline=datetime.now(),
            materials=[]
        )

    def create_subject(self, group_id: int, subject_in: SubjectCreate) -> Subject:
        """Create a new subject"""
        subject = Subject(
            id=None,  # ID will be assigned by the database
            name=subject_in.name,
            deadline=subject_in.deadline,
            materials=subject_in.materials
        )
        return self.repository.insert_subject(group_id, subject)

    def update_subject(self, group_id: int, subject_id: int, subject_update: SubjectUpdate) -> Subject:
        """Update subject information"""
        existing_subject = self.repository.get_subject_by_id(group_id, subject_id)
        if not existing_subject:
            raise ValueError(f"Subject with ID {subject_id} not found")

        updated_subject = Subject(
            id=subject_id,
            name=subject_update.name or existing_subject.name,
            deadline=subject_update.deadline or existing_subject.deadline,
            materials=subject_update.materials if subject_update.materials is not None else existing_subject.materials
        )
        return self.repository.update_subject(group_id, updated_subject)

    def delete_subject(self, group_id: int, subject_id: int) -> dict:
        """Delete a subject"""
        self.repository.delete_subject(group_id, subject_id)
        return {
            "message": f"Subject {subject_id} for group {group_id} deleted successfully"
        }

# Singleton instance
subject_service = SubjectService()
