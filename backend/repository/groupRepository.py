from sqlalchemy.orm import Session
from model.group import Group as GroupModel, group_users
from model.user import User as UserModel
from typing import Optional, List

class GroupRepository:
    """Repository for Group database operations"""

    @staticmethod
    def create_group(db: Session, name: str, description: Optional[str] = None) -> GroupModel:
        """Create a new group"""
        group = GroupModel(
            name=name,
            description=description
        )
        db.add(group)
        db.commit()
        db.refresh(group)
        return group

    @staticmethod
    def get_group_by_id(db: Session, group_id: int) -> Optional[GroupModel]:
        """Get group by ID"""
        return db.query(GroupModel).filter(GroupModel.id == group_id).first()

    @staticmethod
    def get_all_groups(db: Session, skip: int = 0, limit: int = 100) -> List[GroupModel]:
        """Get all groups with pagination"""
        return db.query(GroupModel).offset(skip).limit(limit).all()

    @staticmethod
    def update_group(db: Session, group_id: int, name: Optional[str] = None,
                    description: Optional[str] = None) -> Optional[GroupModel]:
        """Update group information"""
        group = GroupRepository.get_group_by_id(db, group_id)
        if group:
            if name:
                group.name = name
            if description:
                group.description = description
            db.commit()
            db.refresh(group)
        return group

    @staticmethod
    def delete_group(db: Session, group_id: int) -> bool:
        """Delete a group"""
        group = GroupRepository.get_group_by_id(db, group_id)
        if group:
            db.delete(group)
            db.commit()
            return True
        return False

    @staticmethod
    def add_user_to_group(db: Session, group_id: int, user_id: int) -> Optional[GroupModel]:
        """Add a user to a group"""
        group = GroupRepository.get_group_by_id(db, group_id)
        user = db.query(UserModel).filter(UserModel.id == user_id).first()

        if group and user:
            if user not in group.users:
                group.users.append(user)
                db.commit()
                db.refresh(group)
        return group

    @staticmethod
    def remove_user_from_group(db: Session, group_id: int, user_id: int) -> Optional[GroupModel]:
        """Remove a user from a group"""
        group = GroupRepository.get_group_by_id(db, group_id)
        user = db.query(UserModel).filter(UserModel.id == user_id).first()

        if group and user:
            if user in group.users:
                group.users.remove(user)
                db.commit()
                db.refresh(group)
        return group

    @staticmethod
    def get_group_members(db: Session, group_id: int) -> List[UserModel]:
        """Get all members of a group"""
        group = GroupRepository.get_group_by_id(db, group_id)
        if group:
            return group.users
        return []

    @staticmethod
    def get_user_groups(db: Session, user_id: int) -> List[GroupModel]:
        """Get all groups that a user belongs to"""
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if user:
            return user.groups
        return []

