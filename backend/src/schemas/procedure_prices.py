from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProcedurePriceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProcedurePriceItem(ProcedurePriceModel):
    procedure_id: int
    procedure_name: str
    unit_price: Decimal | None
    referenced: bool


class ProcedurePriceScope(ProcedurePriceModel):
    product_id: int
    product_version: int
    product_name: str
    factory_code: str
    product_bom_id: int | None
    origin_flow_node_id: str
    flow_node_id: str
    workshop_id: int
    workshop_name: str
    part_name: str
    part_no: str
    procedures: list[ProcedurePriceItem]


class ProcedurePriceListEnvelope(ProcedurePriceModel):
    data: list[ProcedurePriceScope]
    total: int


class ProcedurePriceInput(ProcedurePriceModel):
    procedure_id: int | None = Field(default=None, gt=0)
    procedure_name: str = Field(min_length=1, max_length=200)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class ProcedurePriceUpdate(ProcedurePriceModel):
    procedures: list[ProcedurePriceInput] = Field(default_factory=list, max_length=100)
