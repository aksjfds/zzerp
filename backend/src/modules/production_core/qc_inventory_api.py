"""Narrow production-owner API for QC warehouse placement."""

from dataclasses import dataclass

from domain.warehouse import WarehouseItemType
from modules.errors import DomainError
from modules.production_core.context_api import (
    InspectionBatchContext,
    ProductionItemContext,
    WorkOrderContext,
)
from modules.production_core.flow_api import (
    ProductionFlowContext,
    material_completion_status,
)
from modules.production_core.movements import record_movement


@dataclass(frozen=True, slots=True)
class QcInventoryMaterial:
    item_code: str
    item_name: str
    product_version: int
    item_type: WarehouseItemType
    completion_status: str


def project_qc_inventory_material(
    production_item: ProductionItemContext,
    flow_context: ProductionFlowContext,
    completed_flow_node_id: str,
) -> QcInventoryMaterial:
    item_code, item_name = _inventory_identity(production_item, flow_context)
    completion = material_completion_status(
        flow_context.flow,
        flow_context.nodes,
        production_item.origin_flow_node_id,
        completed_flow_node_id,
    )
    return QcInventoryMaterial(
        item_code=item_code,
        item_name=item_name,
        product_version=production_item.product_version,
        item_type=(
            "part" if production_item.product_bom_id is not None else "assembly"
        ),
        completion_status=completion.completion_status,
    )


def _inventory_identity(
    production_item: ProductionItemContext,
    flow_context: ProductionFlowContext,
) -> tuple[str, str]:
    if flow_context.bom_item is not None:
        return flow_context.bom_item.part_no, flow_context.bom_item.part_name
    origin = flow_context.nodes.get(production_item.origin_flow_node_id)
    if origin is None or origin.get("type") != "assembly":
        raise DomainError(
            "production_context_missing",
            "装配体稳定身份不存在",
            status_code=409,
        )
    item_code = str(origin.get("assembly_code") or "").strip()
    item_name = str(
        origin.get("assembly_name") or origin.get("output_name") or ""
    ).strip()
    if not item_code or not item_name:
        raise DomainError(
            "production_context_missing",
            "装配体编号或名称不完整",
            status_code=409,
        )
    return item_code, item_name


def record_qc_inventory_movement(
    session,
    *,
    production_item: ProductionItemContext,
    work_order: WorkOrderContext,
    batch: InspectionBatchContext,
    quantity: int,
    qc_flow_node_id: str,
    qc_department_id: int,
    warehouse_department_id: int,
) -> None:
    record_movement(
        session,
        production_item=production_item,
        quantity=quantity,
        movement_type="qc_inventory",
        source_flow_node_id=qc_flow_node_id,
        target_flow_node_id=None,
        source_department_id=qc_department_id,
        target_department_id=warehouse_department_id,
        work_order=work_order,
        work_order_batch=batch,
    )


__all__ = [
    "QcInventoryMaterial",
    "project_qc_inventory_material",
    "record_qc_inventory_movement",
]
