from fastapi import APIRouter

userController = APIRouter(
  prefix="/v1/user",
  tags=["Users"]
)

@userController.get("/profile")
def get_profile(user_id: int):
  return {
    "message": f"Profile details for user {user_id}"
  }

@userController.put("/profile")
def update_profile(user_id: int):
  return {
    "message": f"Profile for user {user_id} updated successfully"
  }

@userController.get("/groups")
def list_user_groups(user_id: int):
  return {
    "message": f"List of groups for user {user_id}"
  }

@userController.get("/subjects")
def list_user_subjects(user_id: int):
  return {
    "message": f"List of subjects for user {user_id}"
  }