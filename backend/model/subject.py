from pydantic import BaseModel
from datetime import datetime

class Subject(BaseModel):
    id: int
    name: str
    deadline: datetime
    materials: list[int] = []