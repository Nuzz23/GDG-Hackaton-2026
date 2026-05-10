from sqlalchemy.orm import Session
from model.material import Material as MaterialModel
from model.subject import Subject as SubjectModel
from typing import Optional, List


class MaterialRepository:
    """Repository for Material database operations"""

    @staticmethod
    def upload_material(db: Session, name: str, path: str, subject_id: int,
                        file_size: int = 0) -> MaterialModel:
        """Create a new material record"""
        material = MaterialModel(
            name=name,
            path=path,
            subject_id=subject_id,
            file_size=file_size
        )
        db.add(material)
        db.commit()
        db.refresh(material)
        return material

    @staticmethod
    def get_material_by_id(db: Session, group_id: int, material_id: int) -> Optional[MaterialModel]:
        """
        Get material by ID ensuring it belongs to a subject within the correct group.
        Uses a JOIN with the Subject table for security.
        """
        return db.query(MaterialModel).join(SubjectModel).filter(
            MaterialModel.id == material_id,
            SubjectModel.group_id == group_id
        ).first()

    @staticmethod
    def get_materials_by_subject(db: Session, group_id: int, subject_id: int) -> List[MaterialModel]:
        """List all materials for a subject, gated by group ownership."""
        return db.query(MaterialModel).join(SubjectModel).filter(
            MaterialModel.subject_id == subject_id,
            SubjectModel.group_id == group_id,
        ).order_by(MaterialModel.uploaded_at.desc()).all()

    @staticmethod
    def update_material(db: Session, group_id: int, material_id: int,
                        name: Optional[str] = None,
                        path: Optional[str] = None,
                        file_size: Optional[int] = None) -> Optional[MaterialModel]:
        """Update material information strictly within its group hierarchy"""

        material = MaterialRepository.get_material_by_id(db, group_id, material_id)

        if material:
            if name is not None:
                material.name = name
            if path is not None:
                material.path = path
            if file_size is not None:
                material.file_size = file_size

            db.commit()
            db.refresh(material)

        return material

    @staticmethod
    def delete_material(db: Session, group_id: int, material_id: int) -> bool:
        """Delete a material ensuring it belongs to the correct group hierarchy"""
        material = MaterialRepository.get_material_by_id(db, group_id, material_id)

        if material:
            db.delete(material)
            db.commit()
            return True

        return False