from fastapi import APIRouter

groupController = APIRouter(
  prefix="/v1/group",
  tags=["Groups"]
)

@groupController.get("/list")
def list_groups():
  return {
    "message": "List of groups"
  }


@groupController.get("/{group_id}/members")
def list_group_members(group_id: int):
  return {
    "message": f"List of members for group {group_id}"
  }

@groupController.get("/{group_id}/subjects")
def list_group_subjects(group_id: int):
  return {
    "message": f"List of subjects for group {group_id}"
  }

@groupController.post("/create")
def create_group():
  return {
    "message": "Group created successfully"
  }

@groupController.post("/add")
def add_to_group():
  return {
    "message": "User added to group successfully"
  }

@groupController.get("/{group_id}")
def get_group(group_id: int):
  return {
    "message": f"Details of group {group_id}"
  }

@groupController.put("/{group_id}")
def update_group(group_id: int):
  return {
    "message": f"Group {group_id} updated successfully"
  }

@groupController.delete("/{group_id}")
def delete_group(group_id: int):
  return {
    "message": f"Group {group_id} deleted successfully"
  }

