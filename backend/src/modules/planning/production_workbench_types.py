"""Internal data structures for the production-workbench read model."""

from dataclasses import dataclass, field
from modules.engineering.model_api import Product
from modules.organization.model_api import Workshop
from modules.production_core.flow_api import ProductionFlowContext
from modules.production_core.model_api import ProductionItem, Repository
from modules.production_core.workbench_read_api import AssemblyInputAllocation, PositionActivity
from modules.sales.model_api import Customer, CustomerOrder


StandardKey = tuple[int, str, str]
AssemblyKey = tuple[int, str]


@dataclass(slots=True)
class DisplayData:
    items: dict[int, ProductionItem]
    orders: dict[int, CustomerOrder]
    customers: dict[int, Customer]
    products: dict[int, Product]
    contexts: dict[int, ProductionFlowContext]
    workshops: dict[int, Workshop]


@dataclass(slots=True)
class StandardCandidate:
    key: StandardKey
    repositories: list[Repository] = field(default_factory=list)
    activity: PositionActivity = field(default_factory=PositionActivity)


@dataclass(slots=True)
class AssemblyCandidate:
    key: AssemblyKey
    production_item_ids: set[int] = field(default_factory=set)
    repositories: list[Repository] = field(default_factory=list)
    allocations: list[AssemblyInputAllocation] = field(default_factory=list)
    activity: PositionActivity = field(default_factory=PositionActivity)


@dataclass(frozen=True, slots=True)
class CandidateView:
    candidate: StandardCandidate | AssemblyCandidate
    position_type: str
    position_key: str
    representative_item_id: int
    customer_order_item_id: int
    node: dict
    workshop: Workshop
    available_quantity: int


@dataclass(frozen=True, slots=True)
class AssemblyAvailability:
    capacity_quantity: int
    initial_capacity_quantity: int
    continuation_capacity_quantity: int
    input_materials_complete: bool
    required_material_keys: frozenset[str]
