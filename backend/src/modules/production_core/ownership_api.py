"""Transaction-aware write API for production-core owned records.

Callers provide the current SQLAlchemy session so cross-module workflows keep
their existing atomic transaction without constructing production ORM records
outside this module.
"""

from sqlalchemy import select

from domain.production_types import WORK_ORDER_SUPPLIER_PROCESSING
from domain.time import business_now
from modules.organization.context_api import ProcedureContext
from modules.production_core.persistence import (
    ProductionItem,
    Repository,
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderBatch,
)
from modules.errors import DomainError
from modules.production_core.material_state_api import (
    get_material_state,
    validate_material_state_identity,
)
from domain.time import utc_now


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
    repository_id: int | None,
    production_item_id: int,
    source_processing_state_id: int,
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
        source_processing_state_id=source_processing_state_id,
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
    is_temporary: bool,
    repository_id: int | None = None,
    source_processing_state_id: int | None = None,
) -> WorkOrder:
    order = WorkOrder(
        repository_id=repository_id,
        production_item_id=production_item_id,
        source_processing_state_id=source_processing_state_id,
        procedure_id=procedure.id,
        work_order_type="assembly",
        is_temporary=is_temporary,
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


def create_supplier_processing_work_order_record(
    session,
    *,
    production_item_id: int,
    source_flow_node_id: str,
    supplier_flow_node_id: str,
    supplier_name: str,
    supplier_process_name: str,
    quantity: int,
    created_by: str,
    remark: str | None,
) -> WorkOrder:
    order = WorkOrder(
        repository_id=None,
        production_item_id=production_item_id,
        source_processing_state_id=None,
        procedure_id=None,
        work_order_type=WORK_ORDER_SUPPLIER_PROCESSING,
        is_temporary=False,
        flow_node_id=supplier_flow_node_id,
        source_flow_node_id=source_flow_node_id,
        supplier_name=supplier_name,
        supplier_process_name=supplier_process_name,
        work_order_name=supplier_process_name,
        created_by=created_by,
        remark=(remark or "").strip() or None,
        worker_id=None,
        worker_name=None,
        quantity=quantity,
    )
    session.add(order)
    session.flush()
    order.work_order_no = f"WO-{business_now():%Y%m%d}-{order.id:06d}"
    session.flush()
    return order


def cancel_supplier_processing_work_order_record(
    session,
    *,
    work_order_id: int,
) -> WorkOrder:
    order = session.get(WorkOrder, work_order_id, with_for_update=True)
    if order is None or order.work_order_type != WORK_ORDER_SUPPLIER_PROCESSING:
        raise DomainError("supplier_processing_work_order_not_found", "委外加工工单不存在", status_code=404)
    if order.status != "open":
        raise DomainError("supplier_processing_work_order_not_cancellable", "当前委外加工工单不能取消", status_code=409)
    if session.scalar(select(WorkOrderBatch.id).where(
        WorkOrderBatch.work_order_id == order.id
    ).limit(1)) is not None:
        raise DomainError(
            "supplier_processing_work_order_inspected",
            "委外加工工单已经录入质检结果，不能取消",
            status_code=409,
        )
    order.status = "cancelled"
    order.closed_at = utc_now()
    session.flush()
    return order


def add_repository_quantity(
    session,
    *,
    production_item_id: int,
    processing_state_id: int,
    flow_node_id: str,
    source_flow_node_id: str,
    department_id: int,
    quantity: int,
    source_work_order_id: int | None = None,
) -> Repository | None:
    if quantity <= 0:
        return None
    production_item = session.get(ProductionItem, production_item_id, with_for_update=True)
    if production_item is None:
        raise DomainError("production_context_missing", "生产项不存在", status_code=409)
    validate_material_state_identity(
        get_material_state(session, processing_state_id),
        production_item,
    )
    repository = session.scalar(
        select(Repository)
        .where(
            Repository.production_item_id == production_item_id,
            Repository.processing_state_id == processing_state_id,
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
            processing_state_id=processing_state_id,
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
    "create_supplier_processing_work_order_record",
    "cancel_supplier_processing_work_order_record",
    "create_work_order_material",
]
