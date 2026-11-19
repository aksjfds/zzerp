from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from schemas.planning import PlanningModel


class QcInspectionCreate(PlanningModel):
    source_kind: Literal['handoff', 'return', 'warehouse']
    source_id: int = Field(gt=0)
    good_quantity: int = Field(ge=0, le=9007199254740991, strict=True)
    scrap_quantity: int = Field(ge=0, le=9007199254740991, strict=True)
    rework_quantity: int = Field(ge=0, le=9007199254740991, strict=True)
    repair_department_code: str | None = Field(default=None, min_length=1, max_length=100)
    request_id: UUID
    note: str = Field(default='', max_length=2000)


class QcReworkAction(PlanningModel):
    action: Literal['receive', 'return']
    quantity: int | None = Field(default=None, strict=True, gt=0, le=9007199254740991)
    repaired_quantity: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    unrepaired_quantity: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    request_id: UUID
    note: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def action_quantities(self):
        if self.action == 'receive':
            if self.quantity is None or self.repaired_quantity is not None or self.unrepaired_quantity is not None:
                raise ValueError('接收返修只填写实际接收数量')
        elif self.quantity is not None or self.repaired_quantity is None or self.unrepaired_quantity is None:
            raise ValueError('回交QC须填写修好数及未修好数')
        return self


class QcCommandResult(PlanningModel):
    id: int


class QcCommandEnvelope(PlanningModel):
    data: QcCommandResult


class QcRow(PlanningModel):
    id: int
    work_order_id: int
    source_ref: str = ''
    order_no: str
    product: str
    material: str
    department: str
    quantity: str
    plan_status: str
    created_at: str
    actor_username: str = ''
    note: str = ''
    good_quantity: str = ''
    scrap_quantity: str = ''
    rework_quantity: str = ''
    repair_department: str = ''



class QcTimelineEvent(PlanningModel):
    key: str
    kind: Literal['inspection', 'receive', 'return']
    round: int = Field(ge=0)
    created_at: str
    actor_username: str
    department: str
    quantity: str
    ticket_no: str
    note: str
    repaired_quantity: str
    unrepaired_quantity: str
    inspection: QcRow | None


class QcBatch(PlanningModel):
    id: int
    source_ref: str
    order_no: str
    product: str
    material: str
    quantity: str
    status: Literal['finished', 'awaiting_repair_receipt', 'repairing', 'awaiting_reinspection']
    events: list[QcTimelineEvent]


class QcListEnvelope(PlanningModel):
    data: list[QcBatch]
    total: int


class QcTarget(PlanningModel):
    code: str
    label: str


class QcTargetsEnvelope(PlanningModel):
    data: list[QcTarget]
