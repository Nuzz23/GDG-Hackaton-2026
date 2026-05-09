from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException
from repository.artifactRepository import ArtifactRepository

class ArtifactBase(BaseModel):
    artifact_type: str
    page_number: Optional[int] = None
    content: Dict[str, Any]

class ArtifactCreate(ArtifactBase):
    pass

class ArtifactUpdate(BaseModel):
    artifact_type: Optional[str] = None
    page_number: Optional[int] = None
    content: Optional[Dict[str, Any]] = None

class ArtifactResponse(ArtifactBase):
    id: int
    material_id: int

    class Config:
        from_attributes = True

class ArtifactService:
    """Service layer for material artifact operations"""

    def create_artifact(self, db: Session, material_id: int, artifact_in: ArtifactCreate) -> ArtifactResponse:
        """Create a new artifact"""
        return ArtifactRepository.create_artifact(
            db=db,
            material_id=material_id,
            artifact_type=artifact_in.artifact_type,
            page_number=artifact_in.page_number,
            content=artifact_in.content
        )

    def get_artifact(self, db: Session, material_id: int, artifact_id: int) -> ArtifactResponse:
        """Get artifact by ID"""
        artifact = ArtifactRepository.get_artifact_by_id(db, artifact_id, material_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return artifact

    def get_artifacts_by_material(self, db: Session, material_id: int, artifact_type: Optional[str] = None) -> List[ArtifactResponse]:
        """Get all artifacts for a material"""
        return ArtifactRepository.get_artifacts_by_material(db, material_id, artifact_type)

    def update_artifact(self, db: Session, material_id: int, artifact_id: int, artifact_update: ArtifactUpdate) -> ArtifactResponse:
        """Update artifact information"""
        artifact = ArtifactRepository.update_artifact(
            db=db,
            artifact_id=artifact_id,
            material_id=material_id,
            artifact_type=artifact_update.artifact_type,
            page_number=artifact_update.page_number,
            content=artifact_update.content
        )
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return artifact

    def delete_artifact(self, db: Session, material_id: int, artifact_id: int) -> dict:
        """Delete an artifact"""
        success = ArtifactRepository.delete_artifact(db, artifact_id, material_id)
        if not success:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return {"message": f"Artifact {artifact_id} deleted successfully"}

# Singleton instance
artifact_service = ArtifactService()