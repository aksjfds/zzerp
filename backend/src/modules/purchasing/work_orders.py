from modules.errors import DomainError
from modules.organization.context_api import ProcedureContext
from modules.organization.read_api import get_department_ids_by_codes
from modules.production_core.context_api import (
    InventorySourceContext,
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.operational_api import (
    create_order_record,
    order_remaining_quantity,
    process_qc_node,
    record_movement,
)
from modules.production_core.ownership_api import add_repository_quantity
from modules.production_core.purchase_api import (
    finalize_purchase_submission,
    is_repository_source,
)
from modules.quality.ownership_api import create_inspection_batch
from modules.standard_execution.pricing_api import attach_work_order_price
from modules.standard_execution.procedures import material_key, procedure_department_id


def create_purchase_order(
    session,
    *,
    source: InventorySourceContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext,
    quantity: int,
    worker_id: int | None,
    remark: str | None,
) -> WorkOrderContext:
    if not is_repository_source(source):
        raise DomainError("purchase_source_invalid", "外购入库单只能使用待外购数量")
    order = create_order_record(
        session,
        source=source,
        production_item=production_item,
        procedure=procedure,
        quantity=quantity,
        worker_id=worker_id,
        work_order_type="purchase_receipt",
        remark=remark,
    )
    attach_work_order_price(
        session,
        work_order_id=order.id,
        product_id=production_item.product_id,
        product_version=production_item.product_version,
        material_key=material_key(production_item),
        flow_node_id=source.flow_node_id,
        procedure_id=procedure.id,
        procedure_name=procedure.procedure_name,
    )
    return order


def submit_purchase_order(
    session,
    *,
    order: WorkOrderContext,
    source: InventorySourceContext,
    production_item: ProductionItemContext,
    procedure: ProcedureContext,
    context,
    node: dict,
    quantity: int,
    completion_action: str,
) -> dict:
    if procedure.procedure_type != "purchase_receipt":
        raise DomainError("work_order_type_invalid", "外购入库工单所属工艺无效")
    remaining = order_remaining_quantity(order)
    if quantity <= 0 or quantity > remaining or quantity > source.quantity:
        raise DomainError("submission_quantity_exceeded", "提交数量超过工单剩余数量")

    batch = None
    target_flow_node_id = None
    target_department_id = None
    if completion_action == "qc":
        qc_node = process_qc_node(context.flow, context.nodes, node["id"])
        qc_department_id = get_department_ids_by_codes(session, {"qc"}).get("qc")
        if qc_node is None or qc_department_id is None:
            raise DomainError("work_order_qc_not_configured", "当前工艺后未配置有效QC节点")
        batch = create_inspection_batch(
            session,
            work_order_id=order.id,
            submitted_quantity=quantity,
            source_flow_node_id=order.source_flow_node_id,
        )
        target_flow_node_id = qc_node["id"]
        target_department_id = qc_department_id
    else:
        target_department_id = procedure_department_id(session, procedure)
        add_repository_quantity(
            session,
            production_item_id=production_item.id,
            flow_node_id=node["id"],
            source_flow_node_id=node["id"],
            department_id=target_department_id,
            quantity=quantity,
            source_work_order_id=order.id,
        )
        target_flow_node_id = node["id"]

    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type="purchase_receipt",
        source_flow_node_id=node["id"],
        target_flow_node_id=target_flow_node_id,
        source_department_id=source.department_id,
        target_department_id=target_department_id,
        work_order_id=order.id,
        work_order_batch_id=batch.id if batch else None,
    )
    return finalize_purchase_submission(
        session,
        order=order,
        source=source,
        production_item=production_item,
        quantity=quantity,
    )
