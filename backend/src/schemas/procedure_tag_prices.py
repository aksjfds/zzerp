from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProcedureTagPriceModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class ProcedureTagPriceTagResponse(ProcedureTagPriceModel):
    id: int
    tag_name: str
    unit_price: Decimal | None


class ProcedureTagPriceProcedureResponse(ProcedureTagPriceModel):
    procedure_id: int
    procedure_name: str
    tags_locked: bool
    available_tags: list[ProcedureTagPriceTagResponse]
    configured_tags: list[ProcedureTagPriceTagResponse]


class ProcedureTagPricePartResponse(ProcedureTagPriceModel):
    product_id: int
    product_version: int
    product_name: str
    factory_code: str
    product_bom_id: int | None
    origin_flow_node_id: str
    part_name: str
    part_no: str
    procedures: list[ProcedureTagPriceProcedureResponse]


class ProcedureTagPriceListEnvelope(ProcedureTagPriceModel):
    data: list[ProcedureTagPricePartResponse]
    total: int


class ProcedureTagPriceInput(ProcedureTagPriceModel):
    tag_name: str = Field(min_length=1, max_length=200)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class ProcedureTagPriceUpdate(ProcedureTagPriceModel):
    tags: list[ProcedureTagPriceInput] = Field(default_factory=list, max_length=100)
