from pydantic import BaseModel, ConfigDict


class OrganizationModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DepartmentResponse(OrganizationModel):
    id: int
    department_name: str
    department_code: str


class WorkshopResponse(OrganizationModel):
    id: int
    department_id: int
    workshop_name: str


class ProcedureResponse(OrganizationModel):
    id: int
    workshop_id: int
    procedure_name: str
