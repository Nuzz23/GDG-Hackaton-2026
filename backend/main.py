from fastapi import FastAPI
from contextlib import asynccontextmanager

from controller.artifactController import artifactController
from controller.agentController import agentController
from database import engine, Base, SessionLocal

#from controller.authController import authController
from controller.groupController import groupController
from controller.materialController import materialController
from controller.subjectController import subjectController
from controller.userController import userController


def _seed_default_group():
    """Ensure a usable group exists at startup.

    The current frontend hardcodes `groupId = 1`. Without a row in the
    `groups` table, every attempt to create a subject (or upload material,
    transitively) crashes with a ForeignKeyViolation. We seed a default
    group + user the first time the server boots against an empty DB.
    """
    from model.user import User
    from model.group import Group

    with SessionLocal() as db:
        existing = db.query(Group).filter(Group.id == 1).first()
        if existing:
            return

        # Create default user if none exists
        user = db.query(User).filter(User.username == "john_doe").first()
        if user is None:
            user = User(
                username="john_doe",
                email="john.doe@example.com",
                password_hash="dev-only-not-real",
            )
            db.add(user)
            db.flush()

        group = Group(
            id=1,
            name="Default Study Group",
            description="Auto-seeded at first startup so the demo flow works.",
        )
        group.users.append(user)
        db.add(group)
        db.commit()
        print(f"Seeded default group (id=1) with user '{user.username}'")


# Initialize database tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized!")
    try:
        _seed_default_group()
    except Exception as e:
        print(f"Could not seed default group ({e!r}); continuing without seed.")
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
app.include_router(agentController)

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {"message": "Study Group API is running", "status": "ok"}

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], # Or ["*"] for everything (less secure)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)