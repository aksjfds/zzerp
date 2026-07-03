from domain.enums import RouteStepType
from pydantic import Field

from domain.enums import MasterDataStatus
from schemas.common import ApiSchema


class RouteStepInput(ApiSchema):
    step_type: RouteStepType
    department_id: int | None = None
    workshop_id: int | None = None


class MaterialRouteInput(ApiSchema):
    steps: list[RouteStepInput] = Field(min_length=1)


class RouteStepData(ApiSchema):
    id: int
    sequence_no: int
    step_type: RouteStepType
    department_id: int | None = None
    workshop_id: int | None = None


    department_name: str | None = None
    workshop_name: str | None = None


class MaterialRouteData(ApiSchema):
    id: int
    material_id: int
    material_code: str
    material_name: str
    version_no: int
    status: MasterDataStatus
    steps: list[RouteStepData]
