from enum import Enum
from pydantic import BaseModel, Field

class Procedure(str, Enum):
    LASER = "laser"
    STAMP = "stamp"
    CNC = "cnc"
    POLISH = "polish"
    QC = "qc"

class CreateWorkOrderPayload(BaseModel):
    item: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)
    procedures: list[Procedure] = Field(min_length=1)

class MoveRepositoryQuantityPayload(BaseModel):
    order_id: int = Field(gt=0)
    item: str = Field(min_length=1, max_length=100)
    repository: Procedure
    quantity: int = Field(gt=0)
    operator: str | None = Field(default=None, max_length=100)
    worker: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=255)
