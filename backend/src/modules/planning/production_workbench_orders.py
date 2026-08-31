"""Selected production-position work orders and procedure summaries."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal
from domain.production_types import (
    WORK_ORDER_STATUS_CANCELLED,
    WORK_ORDER_STATUS_OPEN,
)
from domain.production_workbench import ProductionWorkbenchPositionType
from modules.errors import DomainError
from modules.organization.model_api import Department
from modules.production_core.workbench_read_api import (
    WorkbenchPositionWorkOrders,
    WorkbenchWorkOrderProgress,
    load_assembly_position_work_orders,
    load_standard_position_work_orders,
)


@dataclass(slots=True)
class ProcedureSummary:
    procedure_id: int
    procedure_name: str
    is_temporary: bool
    work_order_count: int = 0
    open_work_order_count: int = 0
    work_order_quantity: int = 0
    processing_quantity: int = 0
    ready_for_result_quantity: int = 0
    pending_qc_quantity: int = 0
    qualified_quantity: int = 0
    rework_quantity: int = 0
    scrap_quantity: int = 0
    lost_quantity: int = 0


def list_production_workbench_work_orders(
    department_code: str,
    position_type: ProductionWorkbenchPositionType,
    page: int,
    page_size: int,
    *,
    production_item_id: int | None = None,
    customer_order_item_id: int | None = None,
    flow_node_id: str,
    source_flow_node_id: str | None = None,
    procedure_id: int | None = None,
    is_temporary: bool | None = None,
) -> dict:
    with SessionLocal() as session:
        department = session.scalar(
            select(Department).where(
                Department.department_code == department_code
            )
        )
        if department is None:
            raise DomainError(
                "department_not_found",
                "部门不存在",
                status_code=404,
            )
        snapshot = _load_position_work_orders(
            session,
            department,
            position_type,
            page,
            page_size,
            production_item_id=production_item_id,
            customer_order_item_id=customer_order_item_id,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            procedure_id=procedure_id,
            is_temporary=is_temporary,
        )
        return {
            "data": list(snapshot.work_orders),
            "total": snapshot.total,
            "procedure_summaries": _procedure_summaries(snapshot.progress),
        }


def _load_position_work_orders(
    session: Session,
    department: Department,
    position_type: ProductionWorkbenchPositionType,
    page: int,
    page_size: int,
    *,
    production_item_id: int | None,
    customer_order_item_id: int | None,
    flow_node_id: str,
    source_flow_node_id: str | None,
    procedure_id: int | None,
    is_temporary: bool | None,
) -> WorkbenchPositionWorkOrders:
    if position_type == "standard":
        if production_item_id is None or source_flow_node_id is None:
            raise DomainError(
                "standard_workbench_position_invalid",
                "普通生产位置身份不完整",
            )
        return load_standard_position_work_orders(
            session,
            department_id=department.id,
            production_item_id=production_item_id,
            flow_node_id=flow_node_id,
            source_flow_node_id=source_flow_node_id,
            page=page,
            page_size=page_size,
            procedure_id=procedure_id,
            is_temporary=is_temporary,
        )
    if position_type != "assembly":
        raise DomainError(
            "workbench_position_type_invalid",
            "生产位置类型无效",
        )
    if department.department_code != "assembly":
        raise DomainError(
            "assembly_workbench_department_invalid",
            "只有装配部可以查询多路生产位置",
            status_code=403,
        )
    if customer_order_item_id is None:
        raise DomainError(
            "assembly_workbench_position_invalid",
            "装配生产位置身份不完整",
        )
    return load_assembly_position_work_orders(
        session,
        customer_order_item_id=customer_order_item_id,
        flow_node_id=flow_node_id,
        page=page,
        page_size=page_size,
        procedure_id=procedure_id,
        is_temporary=is_temporary,
    )


def _procedure_summaries(
    progress: tuple[WorkbenchWorkOrderProgress, ...],
) -> list[dict]:
    summaries: dict[tuple[int, bool], ProcedureSummary] = {}
    for item in progress:
        if item.status == WORK_ORDER_STATUS_CANCELLED:
            continue
        key = (item.procedure_id, item.is_temporary)
        summary = summaries.setdefault(
            key,
            ProcedureSummary(
                procedure_id=item.procedure_id,
                procedure_name=item.procedure_name,
                is_temporary=item.is_temporary,
            ),
        )
        summary.work_order_count += 1
        summary.open_work_order_count += int(item.status == WORK_ORDER_STATUS_OPEN)
        summary.work_order_quantity += item.work_order_quantity
        summary.processing_quantity += item.processing_quantity
        summary.ready_for_result_quantity += item.ready_for_result_quantity
        summary.pending_qc_quantity += item.pending_qc_quantity
        summary.qualified_quantity += item.qualified_quantity
        summary.rework_quantity += item.rework_quantity
        summary.scrap_quantity += item.scrap_quantity
        summary.lost_quantity += item.lost_quantity
    return [
        _summary_response(item)
        for _, item in sorted(
            summaries.items(),
            key=lambda entry: (
                entry[1].is_temporary,
                entry[1].procedure_name,
                entry[1].procedure_id,
            ),
        )
    ]


def _summary_response(summary: ProcedureSummary) -> dict:
    return {
        "procedure_id": summary.procedure_id,
        "procedure_name": summary.procedure_name,
        "is_temporary": summary.is_temporary,
        "work_order_count": summary.work_order_count,
        "open_work_order_count": summary.open_work_order_count,
        "work_order_quantity": summary.work_order_quantity,
        "processing_quantity": summary.processing_quantity,
        "ready_for_result_quantity": summary.ready_for_result_quantity,
        "pending_qc_quantity": summary.pending_qc_quantity,
        "qualified_quantity": summary.qualified_quantity,
        "rework_quantity": summary.rework_quantity,
        "scrap_quantity": summary.scrap_quantity,
        "lost_quantity": summary.lost_quantity,
    }


__all__ = ["list_production_workbench_work_orders"]
