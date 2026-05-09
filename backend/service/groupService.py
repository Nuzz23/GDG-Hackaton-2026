from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException
from repository.groupRepository import GroupRepository


class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class GroupResponse(GroupBase):
    id: int

    class Config:
        from_attributes = True


class GroupUserAdd(BaseModel):
    group_id: int
    user_id: int


class GroupService:
    """Service layer for group operations"""

    def list_groups(self, db: Session, skip: int = 0, limit: int = 100) -> List[GroupResponse]:
        """Fetch and return all groups"""
        return GroupRepository.get_all_groups(db, skip=skip, limit=limit)

    def get_group(self, db: Session, group_id: int) -> GroupResponse:
        """Get a specific group by ID"""
        group = GroupRepository.get_group_by_id(db, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        return group

    def create_group(self, db: Session, group_in: GroupCreate) -> GroupResponse:
        """Create a new group"""
        return GroupRepository.create_group(
            db=db,
            name=group_in.name,
            description=group_in.description
        )

    def update_group(self, db: Session, group_id: int, group_update: GroupUpdate) -> GroupResponse:
        """Update group information"""
        group = GroupRepository.update_group(
            db=db,
            group_id=group_id,
            name=group_update.name,
            description=group_update.description
        )
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        return group

    def delete_group(self, db: Session, group_id: int) -> dict:
        """Delete a group"""
        success = GroupRepository.delete_group(db, group_id)
        if not success:
            raise HTTPException(status_code=404, detail="Group not found")
        return {"message": f"Group {group_id} deleted successfully"}

    def add_user_to_group(self, db: Session, payload: GroupUserAdd) -> dict:
        """Add a user to a group"""
        group = GroupRepository.add_user_to_group(db, payload.group_id, payload.user_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group or User not found")
        return {"message": f"User {payload.user_id} added to group {payload.group_id} successfully"}

    def remove_user_from_group(self, db: Session, payload: GroupUserAdd) -> dict:
        """Remove a user from a group"""
        group = GroupRepository.remove_user_from_group(db, payload.group_id, payload.user_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group or User not found")
        return {"message": f"User {payload.user_id} removed from group {payload.group_id} successfully"}


# Singleton instance
group_service = GroupService()