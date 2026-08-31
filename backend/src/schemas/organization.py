from typing import Literal

from pydantic import BaseModel, ConfigDict


class OrganizationModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


DepartmentCapability = Literal[
    "repositories",
    "work_orders",
    "workers",
    "standard_execution",
    "assembly",
    "quality",
    "special_printing",
    "production_progress",
    "production_workbench",
    "inventory",
    "finished_goods",
]


class DepartmentModuleResponse(OrganizationModel):
    code: str
    name: str
    execution_module: str
    capabilities: list[DepartmentCapability]


class DepartmentResponse(OrganizationModel):
    id: int
    department_name: str
    department_code: str


class WorkshopResponse(OrganizationModel):
    id: int
    department_id: int
    workshop_name: str
    input_mode: Literal["single", "multiple"]


class WorkshopRouteResponse(WorkshopResponse):
    department_name: str
    department_code: str


class ProcedureResponse(OrganizationModel):
    id: int
    workshop_id: int
    department_name: str
    department_code: str
    procedure_name: str
