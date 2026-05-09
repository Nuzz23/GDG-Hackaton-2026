from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class Material(Base):
    """Material model for database"""
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, default=0)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    subject = relationship("Subject", back_populates="materials")

    artifacts = relationship("MaterialArtifact", back_populates="material", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Material(id={self.id}, name={self.name}, subject_id={self.subject_id})>"