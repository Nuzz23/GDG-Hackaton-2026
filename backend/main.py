from fastapi import FastAPI, APIRouter

from controller.authController import authController
from controller.groupController import groupController
from controller.materialController import materialController
from controller.subjectController import subjectController
from controller.userController import userController

app = FastAPI()

app.root_path = "/api"

app.include_router(authController)
app.include_router(groupController)
app.include_router(materialController)
app.include_router(subjectController)
app.include_router(userController)