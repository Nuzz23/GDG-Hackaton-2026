from fastapi import FastAPI
from contextlib import asynccontextmanager

from controller.artifactController import artifactController
from database import engine, Base

#from controller.authController import authController
from controller.groupController import groupController
from controller.materialController import materialController
from controller.subjectController import subjectController
from controller.userController import userController

# Initialize database tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized!")
    yield
    # Shutdown (optional cleanup)
    print("Shutting down...")

app = FastAPI(
    title="Study Group API",
    description="API for managing study groups, subjects, and materials",
    version="1.0.0",
    lifespan=lifespan
)

app.root_path = "/api"

# Include routers
#app.include_router(authController)
app.include_router(groupController)
app.include_router(materialController)
app.include_router(subjectController)
app.include_router(userController)
app.include_router(artifactController)

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {"message": "Study Group API is running", "status": "ok"}

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
