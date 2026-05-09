from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any, Dict
from datetime import datetime
from repository.artifactRepository import ArtifactRepository
from model.material_artifact import ArtifactType
from database import SessionLocal


# --- SCHEMAS ---
class ArtifactCreate(BaseModel):
    artifact_type: ArtifactType
    content: Any  # Può essere un dict, una lista, ecc.
    page_number: Optional[int] = None


class ArtifactUpdate(BaseModel):
    content: Optional[Any] = None
    page_number: Optional[int] = None


class ArtifactResponse(BaseModel):
    id: int
    material_id: int
    artifact_type: ArtifactType
    page_number: Optional[int]
    content: Any
    created_at: datetime
    updated_at: Optional[datetime]

    # Per Pydantic v2 (se usi v1 usa `class Config: orm_mode = True`)
    model_config = ConfigDict(from_attributes=True)


# --- SERVICE ---
class ArtifactService:

    def create_artifact(self, material_id: int, artifact_in: ArtifactCreate):
        with SessionLocal() as db:
            # Nota: in un'app robusta potresti voler verificare prima se il material_id esiste
            # chiamando il MaterialRepository prima di procedere con la creazione.

            return ArtifactRepository.create_artifact(
                db=db,
                material_id=material_id,
                artifact_type=artifact_in.artifact_type,
                content=artifact_in.content,
                page_number=artifact_in.page_number
            )

    def get_artifacts_by_material(self, material_id: int, artifact_type: Optional[str] = None):
        with SessionLocal() as db:
            return ArtifactRepository.get_artifacts_by_material(db, material_id, artifact_type)

    def get_artifact(self, material_id: int, artifact_id: int):
        with SessionLocal() as db:
            artifact = ArtifactRepository.get_artifact_by_id(db, material_id, artifact_id)

            if not artifact:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Artefatto non trovato o non appartenente a questo materiale"
                )
            return artifact

    def update_artifact(self, material_id: int, artifact_id: int, artifact_update: ArtifactUpdate):
        with SessionLocal() as db:
            # Estraiamo i campi inviati (ignorando quelli non settati)
            update_data = artifact_update.model_dump(exclude_unset=True)

            if not update_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nessun dato valido fornito per l'aggiornamento"
                )

            updated_artifact = ArtifactRepository.update_artifact(
                db=db,
                material_id=material_id,
                artifact_id=artifact_id,
                content=update_data.get("content"),
                page_number=update_data.get("page_number")
            )

            if not updated_artifact:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Artefatto non trovato o non appartenente a questo materiale"
                )

            return updated_artifact

    def delete_artifact(self, material_id: int, artifact_id: int):
        with SessionLocal() as db:
            success = ArtifactRepository.delete_artifact(db, material_id, artifact_id)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Artefatto non trovato o non appartenente a questo materiale"
                )

            return {"detail": f"Artefatto {artifact_id} eliminato con successo"}


# Istanza esportata per l'uso nel Controller
artifact_service = ArtifactService()