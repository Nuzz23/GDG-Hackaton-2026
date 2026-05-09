from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class Material(BaseModel):
    id: int
    name: str
    uploadDate: datetime
    path: str
    fileSize: int

class MaterialCreate(BaseModel):
    name: str
    path: str
    fileSize: int

class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    fileSize: Optional[int] = None

materialController = APIRouter(
    prefix="/v1/material",
    tags=["Material"]
)

@materialController.post("/upload", response_model=Material)
def upload_material(group_id: int, material_in: MaterialCreate):
    return {
        "id": 101,
        "name": material_in.name,
        "uploadDate": datetime.now(),
        "path": material_in.path,
        "fileSize": material_in.fileSize
    }

@materialController.get("/{material_id}", response_model=Material)
def get_material(group_id: int, material_id: int):
    return {
        "id": material_id,
        "name": "Lecture_Notes.pdf",
        "uploadDate": datetime.now(),
        "path": f"/storage/groups/{group_id}/notes.pdf",
        "fileSize": 2048
    }

@materialController.patch("/{material_id}", response_model=Material)
def update_material(group_id: int, material_id: int, material_update: MaterialUpdate):
    return {
        "id": material_id,
        "name": material_update.name or "Original_Name.pdf",
        "uploadDate": datetime.now(),
        "path": material_update.path or "/original/path",
        "fileSize": material_update.fileSize or 1024
    }

@materialController.delete("/{material_id}")
def delete_material(group_id: int, material_id: int):
    return {
        "message": f"Material {material_id} for group {group_id} deleted successfully"
    }