from fastapi import APIRouter

subjectController = APIRouter(
    prefix="/v1/subject",
    tags=["Subjects"]
)

@subjectController.get("/list")
def list_subjects(group_id: int):
  return {
    "message": f"List of subjects for group {group_id}"
  }

@subjectController.post("/create")
def create_subject(group_id: int):
  return {
    "message": f"Subject created successfully for group {group_id}"
  }

@subjectController.get("/{subject_id}")
def get_subject(group_id: int, subject_id: int):
    return {
        "message": f"Details of subject {subject_id} for group {group_id}"
    }

@subjectController.put("/{subject_id}")
def update_subject(group_id: int, subject_id: int):
    return {
        "message": f"Subject {subject_id} for group {group_id} updated successfully"
    }

@subjectController.delete("/{subject_id}")
def delete_subject(group_id: int, subject_id: int):
    return {
        "message": f"Subject {subject_id} for group {group_id} deleted successfully"
    }
