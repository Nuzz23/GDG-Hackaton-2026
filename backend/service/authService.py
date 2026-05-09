from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from repository.userRepository import UserRepository


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str


class AuthResponse(BaseModel):
    message: str
    token: Optional[str] = None
    user_id: Optional[int] = None


class AuthService:
    """Service layer for authentication operations"""

    def login(self, db: Session, credentials: LoginRequest) -> AuthResponse:
        """Authenticate user with email and password"""
        user = UserRepository.get_user_by_email(db, credentials.email)

        if not user or not UserRepository.verify_password(db, user.id, credentials.password):
            raise HTTPException(status_code=401, detail="Credenziali non valide")

        # TODO: Implementare qui la generazione reale del token JWT
        return AuthResponse(
            message="Login successful",
            token="jwt_token_here",
            user_id=user.id
        )

    def register(self, db: Session, user_data: RegisterRequest) -> AuthResponse:
        """Register a new user"""
        # Verifica se email o username esistono già
        if UserRepository.get_user_by_email(db, user_data.email):
            raise HTTPException(status_code=400, detail="Email già registrata")
        if UserRepository.get_user_by_username(db, user_data.username):
            raise HTTPException(status_code=400, detail="Username già in uso")

        new_user = UserRepository.create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )

        # TODO: Implementare qui la generazione reale del token JWT
        return AuthResponse(
            message="Register successful",
            token="jwt_token_here",
            user_id=new_user.id
        )

    def logout(self, db: Session, user_id: int) -> dict:
        """Logout user"""
        # TODO: Implementare l'invalidazione del token
        return {"message": "Logout successful"}

    def refresh_token(self, token: str) -> AuthResponse:
        """Refresh authentication token"""
        # TODO: Implement token refresh logic
        return AuthResponse(
            message="Token refreshed",
            token="new_jwt_token_here"
        )


# Singleton instance
auth_service = AuthService()