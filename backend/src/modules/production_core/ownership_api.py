"""Transaction-aware write API for production-core owned records.

Callers provide the current SQLAlchemy session so cross-module workflows keep
their existing atomic transaction without constructing production ORM records
outside this module.
"""

from sqlalchemy import select

from modules.organization.context_api import ProcedureContext
from modules.production_core.persistence import (
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderMaterial,
)


def create_production_item(
    session,
    *,
    customer_order_item_id: int,
    product_id: int,
    product_version: int,
    product_bom_id: int | None,
    origin_flow_node_id: str,
) -> ProductionItem:
    item = ProductionItem(
        customer_order_item_id=customer_order_item_id,
        product_id=product_id,
        product_version=product_version,
        product_bom_id=product_bom_id,
        origin_flow_node_id=origin_flow_node_id,
    )
    session.add(item)
    session.flush()
    return item


def create_work_order_material(
    session,
    *,
    work_order_id: int,
    repository_id: int,
    production_item_id: int,
    quantity: int,
    source_flow_node_id: str,
    source_previous_flow_node_id: str,
    source_department_id: int,
    source_work_order_id: int | None,
) -> WorkOrderMaterial:
    material = WorkOrderMaterial(
        work_order_id=work_order_id,
        repository_id=repository_id,
        production_item_id=production_item_id,
        quantity=quantity,
        source_flow_node_id=source_flow_node_id,
        source_previous_flow_node_id=source_previous_flow_node_id,
        source_department_id=source_department_id,
        source_work_order_id=source_work_order_id,
    )
    session.add(material)
    return material


def assign_work_order_material_repository(
    material: WorkOrderMaterial,
    repository_id: int | None,
) -> None:
    material.repository_id = repository_id


def assign_work_order_repository(
    order: WorkOrder,
    repository_id: int | None,
) -> None:
    order.repository_id = repository_id


def create_assembly_work_order_record(
    session,
    *,
    production_item_id: int,
    procedure: ProcedureContext,
    flow_node_id: str,
    work_order_name: str,
    created_by: str,
    worker_id: int | None,
    worker_name: str | None,
    quantity: int,
    remark: str | None,
    repository_id: int | None = None,
) -> WorkOrder:
    order = WorkOrder(
        repository_id=repository_id,
        production_item_id=production_item_id,
        procedure_id=procedure.id,
        work_order_type="assembly",
        flow_node_id=flow_node_id,
        source_flow_node_id=flow_node_id,
        work_order_name=work_order_name,
        created_by=created_by,
        remark=(remark or "").strip() or None,
        worker_id=worker_id,
        worker_name=worker_name,
        quantity=quantity,
    )
    session.add(order)
    session.flush()
    return order


def add_repository_quantity(
    session,
    *,
    production_item_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
    department_id: int,
    quantity: int,
    source_work_order_id: int | None = None,
) -> Repository | None:
    if quantity <= 0:
        return None
    session.get(ProductionItem, production_item_id, with_for_update=True)
    repository = session.scalar(
        select(Repository)
        .where(
            Repository.production_item_id == production_item_id,
            Repository.flow_node_id == flow_node_id,
            Repository.source_flow_node_id == source_flow_node_id,
            Repository.department_id == department_id,
            Repository.source_work_order_id == source_work_order_id,
        )
        .with_for_update()
    )
    if repository is None:
        repository = Repository(
            production_item_id=production_item_id,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            department_id=department_id,
            source_work_order_id=source_work_order_id,
            quantity=quantity,
        )
        session.add(repository)
    else:
        repository.quantity += quantity
    return repository


__all__ = [
    "add_repository_quantity",
    "assign_work_order_material_repository",
    "assign_work_order_repository",
    "create_assembly_work_order_record",
    "create_production_item",
    "create_work_order_material",
]
