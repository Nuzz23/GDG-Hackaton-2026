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
    def get_subject_by_id(db: Session, group_id: int, subject_id: int) -> Optional[SubjectModel]:
        """Get subject by ID ensuring it belongs to the correct group"""
        return db.query(SubjectModel).filter(
            SubjectModel.id == subject_id,
            SubjectModel.group_id == group_id
        ).first()

    @staticmethod
    def get_subjects_by_group(db: Session, group_id: int, skip: int = 0,
                              limit: int = 100) -> List[SubjectModel]:
        """Get all subjects for a specific group"""
        return db.query(SubjectModel).filter(
            SubjectModel.group_id == group_id
        ).offset(skip).limit(limit).all()

    @staticmethod
    def get_all_subjects(db: Session, skip: int = 0, limit: int = 100) -> List[SubjectModel]:
        """Get all subjects globally with pagination (Admin use case)"""
        return db.query(SubjectModel).offset(skip).limit(limit).all()

    @staticmethod
    def update_subject(db: Session, group_id: int, subject_id: int,
                       name: Optional[str] = None,
                       description: Optional[str] = None,
                       deadline: Optional[datetime] = None) -> Optional[SubjectModel]:
        """Update subject information strictly within its group"""
        # Utilizza il metodo di ricerca sicuro che controlla anche il group_id
        subject = SubjectRepository.get_subject_by_id(db, group_id, subject_id)

        if subject:
            # Usiamo 'is not None' per permettere lo svuotamento di stringhe o passaggi intenzionali
            if name is not None:
                subject.name = name
            if description is not None:
                subject.description = description
            if deadline is not None:
                subject.deadline = deadline

            db.commit()
            db.refresh(subject)

        return subject

    @staticmethod
    def delete_subject(db: Session, group_id: int, subject_id: int) -> bool:
        """Delete a subject ensuring it belongs to the correct group"""
        # Utilizza il metodo di ricerca sicuro che controlla anche il group_id
        subject = SubjectRepository.get_subject_by_id(db, group_id, subject_id)

        if subject:
            db.delete(subject)
            db.commit()
            return True

        return False