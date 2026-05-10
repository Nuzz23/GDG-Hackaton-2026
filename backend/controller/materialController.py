import logging

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form
from typing import List
from service.materialService import material_service, MaterialUpdate

logger = logging.getLogger(__name__)

materialController = APIRouter(
    prefix="/v1/material",
    tags=["Material"]
)


def _safe_background_index(group_id: int, material_id: int) -> None:
    """Run processing_agent indexing in the background after upload.

    Errors are logged but never re-raised — they should not break the
    user-facing upload response. The user can always trigger indexing
    manually from the MaterialDetailView if the background pass failed.
    """
    try:
        # Lazy import to avoid pulling agent deps if /upload is never used.
        from service.agentService import agent_service
        agent_service.index_material(group_id, material_id)
        logger.info(f"Background indexing complete for material {material_id}")
    except Exception:
        logger.exception(
            f"Background indexing failed for material {material_id}; "
            "user can retrigger from the UI"
        )


@materialController.post("/upload")
def upload_material(
    background: BackgroundTasks,
    group_id: int,
    file: UploadFile = File(...),
    name: str = Form(...),
    subject_id: int = Form(...),
):
    print(f"DEBUG: Ricevuto file {file.filename}, name {name}, group {group_id}")
    result = material_service.upload_material(group_id, file, name, subject_id)
    # Auto-trigger indexing as soon as the file is on disk + the row is in DB.
    # This runs in the background — the upload returns immediately.
    material_id = getattr(result, "id", None) or (result.get("id") if isinstance(result, dict) else None)
    if material_id is not None:
        background.add_task(_safe_background_index, group_id, material_id)
    return result


@materialController.get("/list")
def list_materials(group_id: int, subject_id: int):
    """List all materials for a subject (filtered by group ownership)."""
    return material_service.list_materials_by_subject(group_id, subject_id)


@materialController.get("/{material_id}")
def get_material(group_id: int, material_id: int):
    return material_service.get_material(group_id, material_id)

@materialController.patch("/{material_id}")
def update_material(group_id: int, material_id: int, material_update: MaterialUpdate):
    return material_service.update_material(group_id, material_id, material_update)

@materialController.delete("/{material_id}")
def delete_material(group_id: int, material_id: int):
    return material_service.delete_material(group_id, material_id)
