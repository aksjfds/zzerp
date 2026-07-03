from enum import StrEnum


class DepartmentType(StrEnum):
    SYSTEM = "system"
    OFFICE = "office"
    PRODUCTION = "production"
    QUALITY = "quality"


class MasterDataStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    INACTIVE = "inactive"


class MaterialType(StrEnum):
    FINISHED = "finished"
    SEMI_FINISHED = "semi_finished"
    SELF_MADE = "self_made"
    PURCHASED = "purchased"


class RouteStepType(StrEnum):
    INTERNAL = "internal"
    EXTERNAL_SURFACE = "external_surface"


class CustomerOrderStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class ProductionPlanStatus(StrEnum):
    DRAFT = "draft"
    RELEASED = "released"
    PRODUCING = "producing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
