from datetime import date

from pydantic import BaseModel, Field


class CreateProductPayload(BaseModel):
    order_id: str = Field(min_length=1)
    zz_code: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    delivery_date: date
    process: list[str] = Field(min_length=1)
    quantity: int = Field(gt=0)


class ProcessStepPayload(BaseModel):
    process_name: str = Field(min_length=1)
    requires_cleaning: bool = False
    requires_qc: bool = False


class ConfigureProcessesPayload(BaseModel):
    product_id: int = Field(gt=0)
    preset_id: int | None = Field(default=None, gt=0)
    steps: list[ProcessStepPayload] = Field(min_length=1)


class SavePolishProcessPresetPayload(BaseModel):
    preset_name: str = Field(min_length=1)
    steps: list[ProcessStepPayload] = Field(min_length=1)
    active: bool = True


class CreateWorkOrderPayload(BaseModel):
    product_id: int = Field(gt=0)
    department: str = Field(min_length=1)
    process_name: str = Field(min_length=1)
    worker_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    rework_request_id: int | None = Field(default=None, gt=0)
    note: str | None = None


class CreateReworkRequestPayload(BaseModel):
    source_work_order_id: int = Field(gt=0)
    source_batch_id: int | None = Field(default=None, gt=0)
    target_department: str = Field(min_length=1)
    target_process_name: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1)


class CreateSubmissionPayload(BaseModel):
    quantity: int = Field(gt=0)


class DirectReportPayload(BaseModel):
    ok_quantity: int = Field(ge=0)
    scrap_quantity: int = Field(ge=0)
    lost_quantity: int = Field(ge=0)
    reason: str | None = None


class AssignQcWorkerPayload(BaseModel):
    qc_worker_id: int = Field(gt=0)


class InspectionPayload(BaseModel):
    ok_quantity: int = Field(ge=0)
    rework_quantity: int = Field(ge=0)
    scrap_quantity: int = Field(ge=0)
    lost_quantity: int = Field(ge=0)
    defect_reason: str | None = None


class CreateWorkerPayload(BaseModel):
    name: str = Field(min_length=1)


class CreateProcedurePayload(BaseModel):
    department: str = Field(min_length=1)
    procedure_name: str = Field(min_length=1)
