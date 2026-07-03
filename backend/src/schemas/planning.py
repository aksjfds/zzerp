from datetime import date

from pydantic import Field, model_validator

from domain.enums import MaterialType, ProductionPlanStatus
from schemas.common import ApiSchema


class PlanOrderItemInput(ApiSchema):
    customer_order_item_id: int
    planned_finished_quantity: int = Field(gt=0)


class PlanMaterialAdjustment(ApiSchema):
    customer_order_item_id: int
    material_id: int
    planned_quantity: int = Field(gt=0)
    adjustment_reason: str | None = None


class ProductionPlanPreviewInput(ApiSchema):
    customer_order_id: int
    items: list[PlanOrderItemInput] = Field(min_length=1)


class ProductionPlanItemsInput(ApiSchema):
    items: list[PlanOrderItemInput] = Field(min_length=1)


class ProductionPlanCreate(ProductionPlanPreviewInput):
    start_date: date
    completion_date: date
    material_adjustments: list[PlanMaterialAdjustment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.completion_date < self.start_date:
            raise ValueError("完成日期不能早于开始日期")
        return self


class ProductionPlanUpdate(ApiSchema):
    start_date: date
    completion_date: date
    items: list[PlanOrderItemInput] = Field(min_length=1)
    material_adjustments: list[PlanMaterialAdjustment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.completion_date < self.start_date:
            raise ValueError("完成日期不能早于开始日期")
        return self


class PlanMaterialData(ApiSchema):
    id: int | None = None
    customer_order_item_id: int
    material_id: int
    material_code: str
    material_name: str
    material_type: MaterialType
    theoretical_quantity: int
    planned_quantity: int
    adjustment_reason: str | None
    semi_finished_version_id: int | None
    route_version_id: int | None


class PlanOrderItemData(ApiSchema):
    id: int | None = None
    customer_order_item_id: int
    factory_code: str
    product_name: str
    customer_product_code: str
    treatment_name: str | None
    order_required_quantity: int
    planned_finished_quantity: int
    stock_quantity: int
    product_bom_version_id: int
    materials: list[PlanMaterialData]


class ProductionPlanPreviewData(ApiSchema):
    customer_order_id: int
    items: list[PlanOrderItemData]


class ProductionPlanData(ProductionPlanPreviewData):
    id: int
    plan_no: str
    customer_name: str
    purchase_order_no: str
    status: ProductionPlanStatus
    start_date: date
    completion_date: date
