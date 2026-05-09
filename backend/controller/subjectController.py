from fastapi import APIRouter
from typing import List
from service.subjectService import (
    subject_service, SubjectCreate, SubjectUpdate
)
from model.subject import Subject

subjectController = APIRouter(
    prefix="/v1/subject",
    tags=["Subjects"]
)

@subjectController.get("/list")
def list_subjects(group_id: int):
    return subject_service.list_subjects(group_id)

@subjectController.post("/create")
def create_subject(group_id: int, subject_in: SubjectCreate):
    return subject_service.create_subject(group_id, subject_in)

@subjectController.get("/{subject_id}")
def get_subject(group_id: int, subject_id: int):
    return subject_service.get_subject(group_id, subject_id)

@subjectController.patch("/{subject_id}")
def update_subject(group_id: int, subject_id: int, subject_update: SubjectUpdate):
    return subject_service.update_subject(group_id, subject_id, subject_update)

@subjectController.delete("/{subject_id}")
def delete_subject(group_id: int, subject_id: int):
    return subject_service.delete_subject(group_id, subject_id)
