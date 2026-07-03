from schemas.common import ApiSchema


class WorkshopCreate(ApiSchema):
    department_id: int
    workshop_code: str
    workshop_name: str


class WorkshopUpdate(ApiSchema):
    workshop_name: str | None = None
    active: bool | None = None


class DepartmentSummary(ApiSchema):
    id: int
    department_code: str
    department_name: str
    department_type: str
    active: bool


class WorkshopSummary(ApiSchema):
    id: int
    department_id: int
    workshop_code: str
    workshop_name: str
    active: bool
