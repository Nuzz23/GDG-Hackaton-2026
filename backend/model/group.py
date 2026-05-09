from pydantic import BaseModel
from datetime import datetime

class Group(BaseModel):
    id: int
    name: str
    creationDate: datetime
    users: list[int] = []