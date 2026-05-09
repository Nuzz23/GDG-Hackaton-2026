from sqlalchemy.orm import Session
from model.material import Material as MaterialModel
from typing import Optional, List

class MaterialRepository:
    """Repository for Material database operations"""

    @staticmethod
    def create_material(db: Session, name: str, path: str, subject_id: int,
                       file_size: int = 0) -> MaterialModel:
        """Create a new material"""
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
    def get_material_by_id(db: Session, material_id: int) -> Optional[MaterialModel]:
        """Get material by ID"""
        return db.query(MaterialModel).filter(MaterialModel.id == material_id).first()

    @staticmethod
    def get_materials_by_subject(db: Session, subject_id: int, skip: int = 0,
                                limit: int = 100) -> List[MaterialModel]:
        """Get all materials for a subject"""
        return db.query(MaterialModel).filter(
            MaterialModel.subject_id == subject_id
        ).offset(skip).limit(limit).all()

    @staticmethod
    def get_all_materials(db: Session, skip: int = 0, limit: int = 100) -> List[MaterialModel]:
        """Get all materials with pagination"""
        return db.query(MaterialModel).offset(skip).limit(limit).all()

    @staticmethod
    def update_material(db: Session, material_id: int, name: Optional[str] = None,
                       path: Optional[str] = None, file_size: Optional[int] = None) -> Optional[MaterialModel]:
        """Update material information"""
        material = MaterialRepository.get_material_by_id(db, material_id)
        if material:
            if name:
                material.name = name
            if path:
                material.path = path
            if file_size is not None:
                material.file_size = file_size
            db.commit()
            db.refresh(material)
        return material

    @staticmethod
    def delete_material(db: Session, material_id: int) -> bool:
        """Delete a material"""
        material = MaterialRepository.get_material_by_id(db, material_id)
        if material:
            db.delete(material)
            db.commit()
            return True
        return False

