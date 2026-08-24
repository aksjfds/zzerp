from typing import Literal, Self

from pydantic import Field, model_validator

from domain.production_types import QcQualifiedDisposition
from schemas.production_base import ProductionModel


class QcInspection(ProductionModel):
    qc_worker_id: int = Field(gt=0)
    qualified_quantity: int = Field(ge=0)
    rework_quantity: int = Field(ge=0)
    scrap_quantity: int = Field(ge=0)
    lost_quantity: int = Field(ge=0)
    defect_reason: str | None = None
    qualified_disposition: QcQualifiedDisposition | None = None

    @model_validator(mode="after")
    def validate_disposition(self) -> Self:
        if (self.qualified_quantity > 0) != (self.qualified_disposition is not None):
            raise ValueError("存在合格数量时必须且只能选择一个合格品去向")
        return self


class WorkOrderBatchResponse(ProductionModel):
    id: int
    work_order_id: int
    submitted_quantity: int
    source_flow_node_id: str
    rework_source_batch_id: int | None
    rework_pending_quantity: int
    qualified_quantity: int | None
    rework_quantity: int | None
    scrap_quantity: int | None
    lost_quantity: int | None
    qc_worker_id: int | None
    qc_worker_name: str | None
    defect_reason: str | None
    qualified_disposition: Literal["return", "release"] | None
    recorded_at: str | None


class WorkOrderBatchEnvelope(ProductionModel):
    data: WorkOrderBatchResponse


class PendingQcResponse(WorkOrderBatchResponse):
    repository_id: int | None
    production_item_id: int
    work_order_no: str
    customer_order_no: str
    part_no: str
    part_name: str
    work_order_name: str


class PendingQcListEnvelope(ProductionModel):
    data: list[PendingQcResponse]
    total: int
