from fastapi import APIRouter
from typing import List
from service.materialService import (
    material_service, MaterialCreate, MaterialUpdate
)
from model.material import Material

materialController = APIRouter(
    prefix="/v1/material",
    tags=["Material"]
)

@materialController.post("/upload")
def upload_material(group_id: int, material_in: MaterialCreate):
    return material_service.upload_material(group_id, material_in)

@materialController.get("/{material_id}")
def get_material(group_id: int, material_id: int):
    return material_service.get_material(group_id, material_id)

@materialController.patch("/{material_id}")
def update_material(group_id: int, material_id: int, material_update: MaterialUpdate):
    return material_service.update_material(group_id, material_id, material_update)

@materialController.delete("/{material_id}")
def delete_material(group_id: int, material_id: int):
    return material_service.delete_material(group_id, material_id)
