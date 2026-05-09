from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger, Text, Enum
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from database import Base

class ArtifactType(enum.Enum):
    HIGHLIGHT = "highlight"
    MINDMAP = "mindmap"
    KEYWORD = "keyword"
    NOTE = "note"
    QUESTION = "question"

class MaterialArtifact(Base):
    """Artifacts associated with a material (highlights, mindmaps, keywords, etc.)"""
    __tablename__ = "material_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey('materials.id'), nullable=False)

    artifact_type = Column(Enum(ArtifactType), nullable=False, index=True)

    page_number = Column(Integer, nullable=True)

    content = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    material = relationship("Material", back_populates="artifacts")

    def __repr__(self):
        return f"<MaterialArtifact(id={self.id}, type={self.artifact_type}, material_id={self.material_id})>"