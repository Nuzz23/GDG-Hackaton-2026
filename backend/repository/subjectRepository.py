from sqlalchemy.orm import Session
from model.subject import Subject as SubjectModel
from typing import Optional, List
from datetime import datetime

class SubjectRepository:
    """Repository for Subject database operations"""

    @staticmethod
    def create_subject(db: Session, name: str, group_id: int,
                      description: Optional[str] = None,
                      deadline: Optional[datetime] = None) -> SubjectModel:
        """Create a new subject"""
        subject = SubjectModel(
            name=name,
            group_id=group_id,
            description=description,
            deadline=deadline
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)
        return subject

    @staticmethod
    def get_subject_by_id(db: Session, subject_id: int) -> Optional[SubjectModel]:
        """Get subject by ID"""
        return db.query(SubjectModel).filter(SubjectModel.id == subject_id).first()

    @staticmethod
    def get_subjects_by_group(db: Session, group_id: int, skip: int = 0,
                             limit: int = 100) -> List[SubjectModel]:
        """Get all subjects for a group"""
        return db.query(SubjectModel).filter(
            SubjectModel.group_id == group_id
        ).offset(skip).limit(limit).all()

    @staticmethod
    def get_all_subjects(db: Session, skip: int = 0, limit: int = 100) -> List[SubjectModel]:
        """Get all subjects with pagination"""
        return db.query(SubjectModel).offset(skip).limit(limit).all()

    @staticmethod
    def update_subject(db: Session, subject_id: int, name: Optional[str] = None,
                      description: Optional[str] = None,
                      deadline: Optional[datetime] = None) -> Optional[SubjectModel]:
        """Update subject information"""
        subject = SubjectRepository.get_subject_by_id(db, subject_id)
        if subject:
            if name:
                subject.name = name
            if description:
                subject.description = description
            if deadline:
                subject.deadline = deadline
            db.commit()
            db.refresh(subject)
        return subject

    @staticmethod
    def delete_subject(db: Session, subject_id: int) -> bool:
        """Delete a subject"""
        subject = SubjectRepository.get_subject_by_id(db, subject_id)
        if subject:
            db.delete(subject)
            db.commit()
            return True
        return False

