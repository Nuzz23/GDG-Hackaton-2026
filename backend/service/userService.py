from typing import Optional, List
from pydantic import BaseModel, EmailStr
from repository.userRepository import UserRepository

class User(BaseModel):
    id: int
    username: str
    email: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None

class UserService:
    """Service layer for user operations"""

    def __init__(self):
        self.repository = UserRepository()

    def get_profile(self, user_id: int) -> User:
        """Retrieve user profile by user_id"""
        # TODO: Implement database query
        return User(
            id=user_id,
            username="mario_rossi",
            email="mario@example.com",
        )

    def update_profile(self, user_id: int, user_data: UserUpdate) -> User:
        """Update user profile"""
        # TODO: Implement database update
        return User(
            id=user_id,
            username=user_data.username or "mario_rossi",
            email=user_data.email or "mario@example.com"
        )

    def list_user_groups(self, user_id: int) -> List[str]:
        """Get list of groups for a user"""
        # TODO: Implement database query
        return ["admin", "editor"]

    def list_user_subjects(self, user_id: int) -> dict:
        """Get list of subjects for a user"""
        # TODO: Implement database query
        return {
            "user_id": user_id,
            "subjects": ["Math", "Science"]
        }

    def list_users(self):
        """Logic to fetch and return all users"""
        # TODO: Implement database query
        pass

    def create_user(self, user_data):
        """Create a new user"""
        return self.repository.insert_user(user_data)

    def update_user(self, user_id, user_data):
        """Update user information"""
        return self.repository.update_user(user_id, user_data)

    def delete_user(self, user_id):
        """Delete a user"""
        self.repository.delete_user(user_id)
        return {"message": f"User {user_id} deleted successfully"}

# Singleton instance
user_service = UserService()
