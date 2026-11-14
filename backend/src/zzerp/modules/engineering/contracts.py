from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session


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
    pcs: int = Field(strict=True, gt=0, le=2147483647)
    remark: str | None = Field(default=None, max_length=1000)


class ProductDataFields(ContractModel):
    product_name: str = Field(min_length=1, max_length=200)
    factory_code: str = Field(min_length=1, max_length=200)
    customer_code: str = Field(min_length=1, max_length=200)


class CreateProductPayload(ProductDataFields):
    customer_id: int | None = Field(default=None, gt=0)
    customer_name: str = Field(min_length=1, max_length=200)
    appearance_name: str = Field(min_length=1, max_length=200)
    bom_items: list[BomItemPayload] = Field(min_length=1, max_length=1000)


class UpdateProductPayload(ProductDataFields):
    customer_id: int | None = Field(default=None, gt=0)
    customer_name: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(gt=0)


class ReplaceBomPayload(ContractModel):
    expected_revision: int = Field(gt=0)
    bom_items: list[BomItemPayload] = Field(min_length=1, max_length=1000)


class UpdateProcessFlowPayload(ContractModel):
    expected_revision: int = Field(gt=0)
    appearance_id: int = Field(gt=0)
    process_flow: ProcessFlowPayload


class BomItemResponse(ContractModel):
    id: int
    product_id: int
    part_name: str
    part_no: str
    pcs: int
    remark: str
    sort_order: int


class ProductResponseFields(ProductDataFields):
    customer_id: int
    customer_name: str


class ProductSummaryResponse(ProductResponseFields):
    appearance_names: list[str]
    id: int
    revision: int
    bom_count: int
    design_ready: bool
    design_ready_reason: str
    created_at: str
    updated_at: str


class AppearanceResponse(ContractModel):
    id: int
    appearance_name: str


class AppearancePayload(ContractModel):
    expected_revision: int = Field(gt=0)
    appearance_name: str = Field(min_length=1, max_length=200)
    source_appearance_id: int | None = Field(default=None, gt=0)


class ProductDetailResponse(ProductResponseFields):
    appearance_id: int | None
    appearance_name: str
    appearances: list[AppearanceResponse]
    id: int
    revision: int
    base_info_editable: bool
    appearance_editable: bool
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


class ProductOptionResponse(ContractModel):
    appearance_id: int
    appearance_name: str
    id: int
    customer_id: int
    product_name: str
    factory_code: str


class ProductOptionsEnvelope(ContractModel):
    data: list[ProductOptionResponse]


class ProductDetailEnvelope(ContractModel):
    data: ProductDetailResponse


class ProductAppearancesEnvelope(ContractModel):
    data: list[AppearanceResponse]


@dataclass(frozen=True, slots=True)
class ProductReference:
    id: int
    customer_id: int
    product_name: str
    factory_code: str
    customer_code: str


@dataclass(frozen=True)
class HandoffRoutes:
    successors: dict[tuple[str, str], frozenset[tuple[str, str]]]


@dataclass(frozen=True, slots=True)
class RouteReference:
    product_id: int
    appearance_id: int
    material_node_id: str
    department_node_id: str
    part_no: str
    part_name: str
    unit_requirement: int
    department_code: str


@dataclass(frozen=True, slots=True)
class MaterialPart:
    part_no: str
    part_name: str


@dataclass(frozen=True, slots=True)
class HandoffContext:
    routes: HandoffRoutes
    material_names: dict[str, str]
    receipt_materials: dict[str, frozenset[str]]
    requirements: dict[str, dict[str, int]]
    parts: dict[str, MaterialPart]


class EngineeringCollaborators(Protocol):
    def has_product_reference(self, session: Session, product_id: int) -> bool: ...

    def referenced_route_pairs(
        self, session: Session, product_id: int, appearance_id: int | None = None
    ) -> set[tuple[str, str]]: ...
    def referenced_handoff_pairs(
        self, session: Session, product_id: int, appearance_id: int | None = None
    ) -> set[tuple[str, str, str, str]]: ...
    def referenced_input_nodes(
        self, session: Session, product_id: int, appearance_id: int | None = None
    ) -> set[str]: ...
