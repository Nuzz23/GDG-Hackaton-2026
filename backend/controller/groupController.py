from fastapi import APIRouter
from typing import List
from service.groupService import (
    group_service, GroupCreate, GroupUpdate, GroupUserAdd
)
from model.group import Group

groupController = APIRouter(
    prefix="/v1/group",
    tags=["Groups"]
)

@groupController.get("/list")
def list_groups():
    return group_service.list_groups()

@groupController.get("/{group_id}/members")
def list_group_members(group_id: int):
    return group_service.list_group_members(group_id)

@groupController.get("/{group_id}/subjects")
def list_group_subjects(group_id: int):
    return group_service.list_group_subjects(group_id)

@groupController.post("/create")
def create_group(group_in: GroupCreate):
    return group_service.create_group(group_in)

@groupController.post("/add")
def add_to_group(payload: GroupUserAdd):
    return group_service.add_user_to_group(payload)

@groupController.get("/{group_id}")
def get_group(group_id: int):
    return group_service.get_group(group_id)

@groupController.patch("/{group_id}")
def update_group(group_id: int, group_update: GroupUpdate):
    return group_service.update_group(group_id, group_update)

@groupController.delete("/{group_id}")
def delete_group(group_id: int):
    return group_service.delete_group(group_id)
