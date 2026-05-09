from fastapi import APIRouter
"""
from service.authService import auth_service, LoginRequest, RegisterRequest, AuthResponse
from model.user import User

authController = APIRouter(
  prefix="/v1/auth",
  tags=["Authentication"]
)

@authController.post("/login")
def login(credentials: LoginRequest):
  return auth_service.login(credentials)

@authController.post("/register")
def register(user_data: RegisterRequest):
  return auth_service.register(user_data)

@authController.post("/logout")
def logout(user_id: int):
  return auth_service.logout(user_id)

@authController.post("/refresh")
def refresh_token(token: str):
  return auth_service.refresh_token(token)
"""