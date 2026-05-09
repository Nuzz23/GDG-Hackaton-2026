from sqlalchemy.orm import Session
from model.group import Group as GroupModel
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
        """Get all groups"""
        return db.query(GroupModel).offset(skip).limit(limit).all()

    @staticmethod
    def update_group(db: Session, group_id: int,
                     name: Optional[str] = None,
                     description: Optional[str] = None) -> Optional[GroupModel]:
        """Update group information"""
        group = GroupRepository.get_group_by_id(db, group_id)

        if group:
            if name is not None:
                group.name = name
            if description is not None:
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
    def add_user_to_group(db: Session, group: GroupModel, user: UserModel) -> GroupModel:
        """Add a user to a group using the Many-to-Many relationship"""
        # Aggiungiamo l'utente alla lista 'users' del gruppo se non è già presente
        if user not in group.users:
            group.users.append(user)
            db.commit()
            db.refresh(group)
        return group