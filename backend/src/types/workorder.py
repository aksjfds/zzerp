from enum import Enum
from pydantic import BaseModel, Field

class Procedure(str, Enum):
    LASER = "laser"
    STAMP = "stamp"
    CNC = "cnc"
    POLISH = "polish"
    QC = "qc"

class ProcessStep(BaseModel):
    name: Procedure
    inbound: int
    outbound: int

class CreateWorkOrderPayload(BaseModel):
    item: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)
    procedures: list[Procedure] = Field(min_length=1)
