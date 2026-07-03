from datetime import datetime

from pydantic import Field

from domain.enums import MaterialType, MasterDataStatus
from schemas.common import ApiSchema


class SurfaceTreatmentCreate(ApiSchema):
    customer_name: str
    treatment_name: str


class SurfaceTreatmentUpdate(ApiSchema):
    treatment_name: str | None = None
    active: bool | None = None


class SurfaceTreatmentSummary(ApiSchema):
    id: int
    customer_name: str
    treatment_name: str
    active: bool


class ProductCustomerCodeCreate(ApiSchema):
    customer_name: str
    customer_product_code: str
    treatment_ids: list[int] = Field(default_factory=list)


class ProductCustomerCodeUpdate(ApiSchema):
    treatment_ids: list[int] | None = None
    active: bool | None = None


class MaterialCreate(ApiSchema):
    material_code: str | None = None
    material_name: str
    material_type: MaterialType
    material_grade: str | None = None
    specification: str | None = None
    note: str | None = None


class MaterialUpdate(ApiSchema):
    material_code: str | None = None
    material_type: MaterialType | None = None
    material_name: str | None = None
    material_grade: str | None = None
    specification: str | None = None
    note: str | None = None
    active: bool | None = None


class ProductCreate(ApiSchema):
    factory_code: str
    product_name: str
    customer_codes: list[ProductCustomerCodeCreate]
    materials: list[MaterialCreate] = Field(default_factory=list)


class ProductUpdate(ApiSchema):
    product_name: str | None = None


class ProductSummary(ApiSchema):
    id: int
    factory_code: str
    product_name: str
    status: MasterDataStatus
    published_by: int | None = None
    published_at: datetime | None = None


class ProductCustomerCodeSummary(ApiSchema):
    id: int
    product_id: int
    customer_name: str
    customer_product_code: str
    active: bool


class MaterialSummary(ApiSchema):
    id: int
    product_id: int
    material_code: str
    material_name: str
    material_type: MaterialType
    material_grade: str | None
    specification: str | None
    note: str | None
    active: bool


class ProductCustomerCodeDetail(ProductCustomerCodeSummary):
    treatment_ids: list[int]


class ProductDetail(ProductSummary):
    customer_codes: list[ProductCustomerCodeDetail]
    materials: list[MaterialSummary]
