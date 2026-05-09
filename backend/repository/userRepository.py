from sqlalchemy.orm import Session
from model.user import User as UserModel
from typing import Optional, List
import hashlib

class UserRepository:
    """Repository for User database operations"""

    @staticmethod
    def create_user(db: Session, username: str, email: str, password: str) -> UserModel:
        """Create a new user"""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        user = UserModel(
            username=username,
            email=email,
            password_hash=password_hash
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[UserModel]:
        """Get user by ID"""
        return db.query(UserModel).filter(UserModel.id == user_id).first()

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[UserModel]:
        """Get user by email"""
        return db.query(UserModel).filter(UserModel.email == email).first()

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[UserModel]:
        """Get user by username"""
        return db.query(UserModel).filter(UserModel.username == username).first()

    @staticmethod
    def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[UserModel]:
        """Get all users with pagination"""
        return db.query(UserModel).offset(skip).limit(limit).all()

    @staticmethod
    def update_user(db: Session, user_id: int, username: Optional[str] = None,
                   email: Optional[str] = None) -> Optional[UserModel]:
        """Update user information"""
        user = UserRepository.get_user_by_id(db, user_id)
        if user:
            if username:
                user.username = username
            if email:
                user.email = email
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        """Delete a user"""
        user = UserRepository.get_user_by_id(db, user_id)
        if user:
            db.delete(user)
            db.commit()
            return True
        return False

    @staticmethod
    def verify_password(db: Session, user_id: int, password: str) -> bool:
        """Verify user password"""
        user = UserRepository.get_user_by_id(db, user_id)
        if user:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            return user.password_hash == password_hash
        return False

