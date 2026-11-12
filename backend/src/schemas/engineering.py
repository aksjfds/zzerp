from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class PointPayload(ContractModel):
    x: float
    y: float


class FlowNodeBase(ContractModel):
    id: str = Field(min_length=1, max_length=100)
    x: float
    y: float
    label: str = Field(min_length=1, max_length=500)
    label_position: PointPayload | None = None
    z_index: int | None = None
    rotation: float | None = None


class PartNodePayload(FlowNodeBase):
    type: Literal["part"]
    bom_item_id: int = Field(gt=0)


class DepartmentNodePayload(FlowNodeBase):
    type: Literal["department"]
    department_code: str = Field(min_length=1, max_length=50)


FlowNodePayload = Annotated[PartNodePayload | DepartmentNodePayload, Field(discriminator="type")]


class FlowEdgePayload(ContractModel):
    id: str = Field(min_length=1, max_length=100)
    edge_type: Literal["polyline"] = "polyline"
    source_node_id: str = Field(min_length=1, max_length=100)
    target_node_id: str = Field(min_length=1, max_length=100)
    source_anchor_id: str | None = None
    target_anchor_id: str | None = None
    start_point: PointPayload | None = None
    end_point: PointPayload | None = None
    points: list[PointPayload] | None = None
    label: str | None = Field(default=None, max_length=200)
    label_position: PointPayload | None = None
    z_index: int | None = None


class ProcessFlowPayload(ContractModel):
    schema_version: Literal[8] = 8
    nodes: list[FlowNodePayload] = Field(default_factory=list, max_length=500)
    edges: list[FlowEdgePayload] = Field(default_factory=list, max_length=2000)


class BomItemPayload(ContractModel):
    id: int | None = Field(default=None, gt=0)
    part_name: str = Field(min_length=1, max_length=200)
    part_no: str = Field(min_length=1, max_length=200)
    pcs: int = Field(gt=0)
    remark: str | None = Field(default=None, max_length=1000)


class ProductDataFields(ContractModel):
    product_name: str = Field(min_length=1, max_length=200)
    factory_code: str = Field(min_length=1, max_length=200)
    customer_code: str = Field(min_length=1, max_length=200)


class CreateProductPayload(ProductDataFields):
    customer_id: int | None = Field(default=None, gt=0)
    customer_name: str = Field(min_length=1, max_length=200)
    bom_items: list[BomItemPayload] = Field(min_length=1, max_length=1000)


class UpdateProductPayload(ProductDataFields):
    customer_id: int | None = Field(default=None, gt=0)
    customer_name: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(gt=0)


class ReplaceBomPayload(ContractModel):
    expected_revision: int = Field(gt=0)
    product_version: int = Field(gt=0)
    bom_items: list[BomItemPayload] = Field(min_length=1, max_length=1000)


class UpdateProcessFlowPayload(ContractModel):
    expected_revision: int = Field(gt=0)
    product_version: int = Field(gt=0)
    process_flow: ProcessFlowPayload


class BomItemResponse(ContractModel):
    id: int
    product_id: int
    product_version: int
    part_name: str
    part_no: str
    pcs: int
    remark: str
    sort_order: int


class ProductResponseFields(ProductDataFields):
    customer_id: int
    customer_name: str


class ProductSummaryResponse(ProductResponseFields):
    id: int
    version: int
    revision: int
    bom_count: int
    design_ready: bool
    design_ready_reason: str
    created_at: str
    updated_at: str


class ProductDetailResponse(ProductResponseFields):
    id: int
    version: int
    current_version: int
    revision: int
    base_info_editable: bool
    version_editable: bool
    design_ready: bool
    design_ready_reason: str
    bom_items: list[BomItemResponse]
    process_flow: ProcessFlowPayload
    process_flow_is_draft: bool
    created_at: str
    updated_at: str


class ProductListEnvelope(ContractModel):
    data: list[ProductSummaryResponse]
    total: int


class ProductDetailEnvelope(ContractModel):
    data: ProductDetailResponse


class ProductVersionsEnvelope(ContractModel):
    data: list[int]
