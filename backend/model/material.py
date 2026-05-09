from pydantic import BaseModel
from datetime import datetime

class Material(BaseModel):
    id: int
    name: str
    uploadDate: datetime
    path: str
    fileSize: int