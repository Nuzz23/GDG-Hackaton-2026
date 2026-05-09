from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from model.material_artifact import MaterialArtifact

class ArtifactRepository:
    """Repository for MaterialArtifact database operations"""

    @staticmethod
    def create_artifact(db: Session, material_id: int, artifact_type: str,
                        content: Dict[str, Any], page_number: Optional[int] = None) -> MaterialArtifact:
        """Create a new artifact for a material"""
        artifact = MaterialArtifact(
            material_id=material_id,
            artifact_type=artifact_type,
            page_number=page_number,
            content=content
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        return artifact

    @staticmethod
    def get_artifact_by_id(db: Session, artifact_id: int, material_id: int) -> Optional[MaterialArtifact]:
        """Get a specific artifact ensuring it belongs to the correct material"""
        return db.query(MaterialArtifact).filter(
            MaterialArtifact.id == artifact_id,
            MaterialArtifact.material_id == material_id
        ).first()

    @staticmethod
    def get_artifacts_by_material(db: Session, material_id: int, artifact_type: Optional[str] = None) -> List[MaterialArtifact]:
        """Get all artifacts for a material, optionally filtered by type"""
        query = db.query(MaterialArtifact).filter(MaterialArtifact.material_id == material_id)
        if artifact_type:
            query = query.filter(MaterialArtifact.artifact_type == artifact_type)
        return query.all()

    @staticmethod
    def update_artifact(db: Session, artifact_id: int, material_id: int,
                        artifact_type: Optional[str] = None,
                        page_number: Optional[int] = None,
                        content: Optional[Dict[str, Any]] = None) -> Optional[MaterialArtifact]:
        """Update artifact information"""
        artifact = ArtifactRepository.get_artifact_by_id(db, artifact_id, material_id)
        if artifact:
            if artifact_type is not None:
                artifact.artifact_type = artifact_type
            if page_number is not None:
                artifact.page_number = page_number
            if content is not None:
                artifact.content = content
            db.commit()
            db.refresh(artifact)
        return artifact

    @staticmethod
    def delete_artifact(db: Session, artifact_id: int, material_id: int) -> bool:
        """Delete an artifact"""
        artifact = ArtifactRepository.get_artifact_by_id(db, artifact_id, material_id)
        if artifact:
            db.delete(artifact)