from sqlalchemy.orm import Session
from model.material_artifact import MaterialArtifact, ArtifactType
from typing import Optional, List, Any, Dict


class ArtifactRepository:
    """Repository for Material Artifact database operations"""

    @staticmethod
    def create_artifact(db: Session, material_id: int, artifact_type: ArtifactType,
                        content: Any, page_number: Optional[int] = None) -> MaterialArtifact:
        """Create a new artifact for a material"""
        artifact = MaterialArtifact(
            material_id=material_id,
            artifact_type=artifact_type,
            content=content,
            page_number=page_number
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        return artifact

    @staticmethod
    def get_artifact_by_id(db: Session, material_id: int, artifact_id: int) -> Optional[MaterialArtifact]:
        """Get a specific artifact, ensuring it belongs to the specified material"""
        return db.query(MaterialArtifact).filter(
            MaterialArtifact.id == artifact_id,
            MaterialArtifact.material_id == material_id
        ).first()

    @staticmethod
    def get_artifacts_by_material(db: Session, material_id: int,
                                  artifact_type: Optional[str] = None) -> List[MaterialArtifact]:
        """Get all artifacts for a material, optionally filtered by type"""
        query = db.query(MaterialArtifact).filter(MaterialArtifact.material_id == material_id)

        if artifact_type:
            # Assicuriamoci di convertire la stringa nell'Enum prima di filtrare
            # In alternativa, SQLAlchemy gestisce spesso la conversione stringa->Enum in automatico,
            # ma è più sicuro passarlo formattato.
            try:
                enum_type = ArtifactType(artifact_type)
                query = query.filter(MaterialArtifact.artifact_type == enum_type)
            except ValueError:
                # Se la stringa passata non corrisponde a nessun Enum, restituiamo lista vuota
                return []

        return query.all()

    @staticmethod
    def update_artifact(db: Session, material_id: int, artifact_id: int,
                        content: Optional[Any] = None,
                        page_number: Optional[int] = None) -> Optional[MaterialArtifact]:
        """Update artifact data strictly within its material"""
        artifact = ArtifactRepository.get_artifact_by_id(db, material_id, artifact_id)

        if artifact:
            if content is not None:
                artifact.content = content
            # Usiamo is not None oppure permettiamo l'azzeramento della pagina passando esplicitamente None?
            # Nel dubbio, aggiorniamo solo se è stato inviato un valore nel dizionario di update.
            if page_number is not None:
                artifact.page_number = page_number

            db.commit()
            db.refresh(artifact)

        return artifact

    @staticmethod
    def delete_artifact(db: Session, material_id: int, artifact_id: int) -> bool:
        """Delete an artifact ensuring it belongs to the correct material"""
        artifact = ArtifactRepository.get_artifact_by_id(db, material_id, artifact_id)

        if artifact:
            db.delete(artifact)
            db.commit()
            return True

        return False