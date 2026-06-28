from datetime import date

from pydantic import BaseModel, Field


class CreateProductPayload(BaseModel):
    order_id: str = Field(min_length=1)
    zz_code: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    delivery_date: date
    process: list[str] = Field(min_length=1)
    quantity: int = Field(gt=0)


class CreateTaskPayload(BaseModel):
    order_id: str = Field(min_length=1)
    zz_code: str = Field(min_length=1)
    product: str = Field(min_length=1)
    worker: str = Field(min_length=1)
    department: str = Field(min_length=1)
    procedure: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    note: str | None = None


class CreateProcedurePayload(BaseModel):
    department: str = Field(min_length=1)
    procedure_name: str = Field(min_length=1)
