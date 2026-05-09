from fastapi import APIRouter

authController = APIRouter(
  prefix="/v1/auth",
  tags=["Authentication"]
)

@authController.get("/login")
def login():
  return {
    "message": "Login successful"
  }

@authController.get("/register")
def register():
  return {
    "message": "Register successful"
  }