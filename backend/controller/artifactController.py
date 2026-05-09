from fastapi import APIRouter, Query
from typing import List, Optional
from service.artifactService import (
    artifact_service, ArtifactCreate, ArtifactUpdate, ArtifactResponse
)

artifactController = APIRouter(
    prefix="/v1/material/{material_id}/artifact",
    tags=["Material Artifact"]
)

@artifactController.post("/")
def create_artifact(material_id: int, artifact_in: ArtifactCreate):
    """
    Crea un nuovo artefatto (nota, sottolineatura, mappa, ecc.) per un documento.
    """
    return artifact_service.create_artifact(material_id, artifact_in)

@artifactController.get("/")
def get_artifacts(
    material_id: int,
    artifact_type: Optional[str] = Query(None, description="Filtra per tipo (es. highlight, mindmap)")
):
    """
    Recupera tutti gli artefatti di un materiale. Può essere filtrato per tipo.
    """
    return artifact_service.get_artifacts_by_material(material_id, artifact_type)

@artifactController.get("/{artifact_id}")
def get_artifact(material_id: int, artifact_id: int):
    """
    Recupera un singolo artefatto specifico.
    """
    return artifact_service.get_artifact(material_id, artifact_id)

@artifactController.patch("/{artifact_id}")
def update_artifact(material_id: int, artifact_id: int, artifact_update: ArtifactUpdate):
    """
    Aggiorna il contenuto o la pagina di un artefatto.
    """
    return artifact_service.update_artifact(material_id, artifact_id, artifact_update)

@artifactController.delete("/{artifact_id}")
def delete_artifact(material_id: int, artifact_id: int):
    """
    Elimina un artefatto.
    """
    return artifact_service.delete_artifact(material_id, artifact_id)