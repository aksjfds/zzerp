from datetime import date

from pydantic import Field

from domain.enums import CustomerOrderStatus
from schemas.common import ApiSchema


class CustomerOrderItemInput(ApiSchema):
    product_customer_code_id: int
    treatment_id: int | None = None
    quantity: int = Field(gt=0)
    delivery_date: date


class CustomerOrderCreate(ApiSchema):
    customer_name: str
    purchase_order_no: str
    order_date: date
    note: str | None = None
    items: list[CustomerOrderItemInput] = Field(min_length=1)


class CustomerOrderUpdate(ApiSchema):
    order_date: date
    note: str | None = None
    items: list[CustomerOrderItemInput] = Field(min_length=1)


class CustomerOrderItemData(ApiSchema):
    id: int
    product_id: int
    factory_code: str
    product_name: str
    product_customer_code_id: int
    customer_product_code: str
    treatment_id: int | None
    treatment_name: str | None
    quantity: int
    delivery_date: date


class CustomerOrderData(ApiSchema):
    id: int
    customer_name: str
    purchase_order_no: str
    version_no: int
    previous_version_id: int | None
    status: CustomerOrderStatus
    order_date: date
    note: str | None
    items: list[CustomerOrderItemData]
