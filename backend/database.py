from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database connection string.
# We default to 127.0.0.1 (IPv4) instead of "localhost" because on Windows
# the resolver often hits ::1 (IPv6) first, and the Docker-compose Postgres
# only binds IPv4 — that combination produces the misleading "server closed
# the connection unexpectedly" error during the SSL handshake.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:admin@127.0.0.1:5432/postgres"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


