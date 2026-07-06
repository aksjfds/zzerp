from datetime import date

from pydantic import BaseModel, ConfigDict


class ProductionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepositoryResponse(ProductionModel):
    id: int
    customer_order_item_id: int
    customer_order_no: str
    customer_name: str
    product_id: int
    product_version: int
    product_name: str
    factory_code: str
    product_bom_id: int
    part_name: str
    part_no: str
    flow_node_id: str
    procedure_name: str
    workshop_name: str
    department_id: int
    department_name: str
    department_code: str
    quantity: int
    delivery_date: date


class RepositoryListEnvelope(ProductionModel):
    data: list[RepositoryResponse]
