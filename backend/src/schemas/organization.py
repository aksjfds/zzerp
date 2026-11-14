from pydantic import BaseModel, ConfigDict


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    name: str
    can_receive: bool
