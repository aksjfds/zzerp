from pydantic import Field

from domain.enums import MasterDataStatus, MaterialType
from schemas.common import ApiSchema


class BomItemInput(ApiSchema):
    material_id: int
    quantity: int = Field(gt=0)


class ProductBomVersionInput(ApiSchema):
    items: list[BomItemInput] = Field(min_length=1)


class BomItemData(ApiSchema):
    id: int
    material_id: int
    material_code: str
    material_name: str
    material_type: MaterialType
    quantity: int
    unit: str = "pcs"


class ProductBomVersionData(ApiSchema):
    id: int
    product_id: int
    version_no: int
    status: MasterDataStatus
    items: list[BomItemData]


class SemiFinishedInputValue(ApiSchema):
    input_material_id: int
    quantity: int = Field(gt=0)


class SemiFinishedVersionInput(ApiSchema):
    quantity_per_finished: int = Field(gt=0)
    inputs: list[SemiFinishedInputValue] = Field(min_length=1)


class SemiFinishedInputData(ApiSchema):
    id: int
    input_material_id: int
    material_code: str
    material_name: str
    material_type: MaterialType
    quantity: int
    unit: str = "pcs"


class SemiFinishedVersionData(ApiSchema):
    id: int
    semi_finished_material_id: int
    material_code: str
    material_name: str
    version_no: int
    quantity_per_finished: int
    status: MasterDataStatus
    inputs: list[SemiFinishedInputData]


class ProductionStructureNode(ApiSchema):
    id: str
    material_id: int
    material_code: str
    material_name: str
    material_type: MaterialType
    quantity: int
    children: list["ProductionStructureNode"] = Field(default_factory=list)


class ProductionStructureData(ApiSchema):
    product_id: int
    bom_version_id: int
    root: ProductionStructureNode
