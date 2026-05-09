from fastapi import APIRouter

materialController = APIRouter(
  prefix="/v1/material",
  tags=["Material"]
)

@materialController.post("/upload")
def upload_material(group_id: int):
  return {
    "message": f"Material uploaded successfully for group {group_id}"
  }

@materialController.get("/{material_id}")
def get_material(group_id: int, material_id: int):
  return {
    "message": f"Details of material {material_id} for group {group_id}"
  }

@materialController.put("/{material_id}")
def update_material(group_id: int, material_id: int):
  return {
    "message": f"Material {material_id} for group {group_id} updated successfully"
  }

@materialController.delete("/{material_id}")
def delete_material(group_id: int, material_id: int):
  return {
    "message": f"Material {material_id} for group {group_id} deleted successfully"
  }