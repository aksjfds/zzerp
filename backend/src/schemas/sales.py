from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SalesModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CustomerOrderItemInput(SalesModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    delivery_date: date
    remark: str | None = Field(default=None, max_length=1000)


class CustomerOrderCreate(SalesModel):
    customer_order_no: str = Field(min_length=1, max_length=200)
    customer_id: int = Field(gt=0)
    remark: str | None = Field(default=None, max_length=1000)
    items: list[CustomerOrderItemInput] = Field(min_length=1, max_length=1000)


class CustomerOrderUpdate(CustomerOrderCreate):
    expected_revision: int = Field(gt=0)
    customer_order_no: str | None = Field(default=None, min_length=1, max_length=200)
    customer_id: int | None = Field(default=None, gt=0)


class CustomerOrderItemResponse(SalesModel):
    id: int
    product_id: int
    product_version: int
    product_name: str
    factory_code: str
    quantity: int
    delivery_date: date
    remark: str


class CustomerOrderProductProgress(SalesModel):
    customer_order_item_id: int
    product_id: int
    product_name: str
    factory_code: str
    total_quantity: int
    completed_quantity: int
    scrap_quantity: int
    lost_quantity: int
    unfinished_quantity: int
    po_shortage_quantity: int


class CustomerOrderResponse(SalesModel):
    id: int
    customer_order_no: str
    customer_id: int
    customer_name: str
    status: str
    revision: int
    remark: str
    items: list[CustomerOrderItemResponse]
    product_progress: list[CustomerOrderProductProgress] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CustomerOrderEnvelope(SalesModel):
    data: CustomerOrderResponse


class CustomerOrderListEnvelope(SalesModel):
    data: list[CustomerOrderResponse]
    total: int
