from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from model.material import Material
from repository.materialRepository import MaterialRepository

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

class MaterialService:
    """Service layer for material operations"""

    def __init__(self):
        self.repository = MaterialRepository()

    def upload_material(self, group_id: int, material_in: MaterialCreate) -> Material:
        """Upload a new material"""
        # TODO: Implement file storage
        material_data = {
            "name": material_in.name,
            "uploadDate": datetime.now(),
            "path": material_in.path,
            "fileSize": material_in.fileSize
        }
        return self.repository.insert_material(material_data)

    def get_material(self, group_id: int, material_id: int) -> Material:
        """Get material by ID"""
        # TODO: Implement database query
        return Material(
            id=material_id,
            name="Lecture_Notes.pdf",
            uploadDate=datetime.now(),
            path=f"/storage/groups/{group_id}/notes.pdf",
            fileSize=2048
        )

    def update_material(self, group_id: int, material_id: int, material_update: MaterialUpdate) -> Material:
        """Update material information"""
        # TODO: Implement database update
        material_data = {
            "name": material_update.name or "Original_Name.pdf",
            "uploadDate": datetime.now(),
            "path": material_update.path or "/original/path",
            "fileSize": material_update.fileSize or 1024
        }
        return self.repository.update_material(material_id, material_data)

    def delete_material(self, group_id: int, material_id: int) -> dict:
        """Delete a material"""
        self.repository.delete_material(material_id)
        return {
            "message": f"Material {material_id} for group {group_id} deleted successfully"
        }

    def list_group_materials(self, group_id: int) -> List[Material]:
        """Get list of materials in a group"""
        # TODO: Implement database query
        return [
            Material(
                id=101,
                name="Lecture_Notes.pdf",
                uploadDate=datetime.now(),
                path=f"/storage/groups/{group_id}/notes.pdf",
                fileSize=2048
            )
        ]

    def list_materials(self):
        # Logic to fetch and return all materials
        pass

# Singleton instance
material_service = MaterialService()
