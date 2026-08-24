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
    "purchasing",
    "assembly",
    "quality",
    "special_printing",
    "production_progress",
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


class WorkshopRouteResponse(WorkshopResponse):
    department_name: str
    department_code: str


class ProcedureResponse(OrganizationModel):
    id: int
    workshop_id: int
    department_name: str
    department_code: str
    procedure_name: str
    procedure_type: Literal["standard", "purchase_receipt"]
    input_mode: Literal["single", "multiple"]
