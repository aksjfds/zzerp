"""Read-only reference checks and projections owned by production core."""

from dataclasses import dataclass
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.orm import Session

from domain.production_types import (
    QcQualifiedDestination,
    STANDARD_EXECUTION_WORK_ORDER_TYPES,
    WORK_ORDER_STATUS_OPEN,
    WORK_ORDER_SUPPLIER_PROCESSING,
    WorkOrderStatus,
)
from modules.errors import DomainError
from modules.production_core.persistence import (
    ProductionItem,
    WorkOrder,
    WorkOrderBatch,
)
from modules.production_core.work_order_status import reserved_quantities
from modules.production_core.work_order_progress import (
    SupplierProcessingQcProgress,
    calculate_supplier_processing_qc_progress,
    validate_supplier_processing_work_order_progress,
)


@dataclass(frozen=True, slots=True)
class PartProductionReference:
    id: int
    customer_order_item_id: int
    product_id: int
    product_version: int
    product_bom_id: int
    origin_flow_node_id: str


@dataclass(frozen=True, slots=True)
class SupplierProcessingWorkOrderReference:
    id: int
    production_item_id: int
    flow_node_id: str
    status: WorkOrderStatus


@dataclass(frozen=True, slots=True)
class TemporaryWorkOrderPriceReference:
    id: int
    work_order_no: str
    product_id: int
    product_version: int
    origin_flow_node_id: str
    flow_node_id: str
    procedure_id: int
    status: WorkOrderStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SupplierProcessingQcBatchReference:
    id: int
    work_order_id: int
    submitted_quantity: int
    source_flow_node_id: str
    qualified_quantity: int
    rework_quantity: int
    scrap_quantity: int
    lost_quantity: int
    qc_worker_id: int
    qc_worker_name: str
    defect_reason: str | None
    qualified_destination: QcQualifiedDestination | None
    destination_decided_at: datetime | None
    destination_decided_by: str | None
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class SupplierProcessingQcOrderReference:
    id: int
    work_order_no: str
    production_item_id: int
    flow_node_id: str
    source_flow_node_id: str
    supplier_name: str
    supplier_process_name: str
    remark: str | None
    quantity: int
    status: WorkOrderStatus
    created_at: datetime
    batches: tuple[SupplierProcessingQcBatchReference, ...]
    qc_progress: SupplierProcessingQcProgress

    @property
    def inspected_quantity(self) -> int:
        return self.qc_progress.inspected_quantity

    @property
    def qualified_quantity(self) -> int:
        return self.qc_progress.qualified_quantity

    @property
    def rework_quantity(self) -> int:
        return self.qc_progress.rework_quantity

    @property
    def scrap_quantity(self) -> int:
        return self.qc_progress.scrap_quantity

    @property
    def lost_quantity(self) -> int:
        return self.qc_progress.lost_quantity

    @property
    def remaining_qualified_quantity(self) -> int:
        return self.qc_progress.remaining_qualified_quantity

    @property
    def pending_destination_quantity(self) -> int:
        return self.qc_progress.pending_destination_quantity

    @property
    def released_quantity(self) -> int:
        return self.qc_progress.released_quantity


PartProductionIdentity = tuple[int, int, int, int, str]
SupplierProcessingPosition = tuple[int, str]


def temporary_work_order_price_references(
    session: Session,
    *,
    procedure_ids: Collection[int],
    offset: int,
    limit: int,
    keyword: str | None,
) -> tuple[list[TemporaryWorkOrderPriceReference], int]:
    if not procedure_ids:
        return [], 0
    statement = (
        select(WorkOrder, ProductionItem)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            WorkOrder.is_temporary.is_(True),
            WorkOrder.work_order_type.in_(list(STANDARD_EXECUTION_WORK_ORDER_TYPES)),
            WorkOrder.procedure_id.in_(list(procedure_ids)),
        )
    )
    value = (keyword or "").strip()
    if value:
        pattern = f"%{value}%"
        statement = statement.where(or_(
            WorkOrder.work_order_no.ilike(pattern),
            WorkOrder.work_order_name.ilike(pattern),
        ))
    total = session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ) or 0
    rows = session.execute(
        statement
        .order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc())
        .offset(offset)
        .limit(limit)
    )
    references: list[TemporaryWorkOrderPriceReference] = []
    for order, production_item in rows:
        if order.work_order_no is None or order.procedure_id is None:
            raise DomainError(
                "temporary_work_order_price_context_invalid",
                "临时工单计价信息不完整",
                status_code=409,
            )
        references.append(TemporaryWorkOrderPriceReference(
            id=order.id,
            work_order_no=order.work_order_no,
            product_id=production_item.product_id,
            product_version=production_item.product_version,
            origin_flow_node_id=production_item.origin_flow_node_id,
            flow_node_id=order.flow_node_id,
            procedure_id=order.procedure_id,
            status=order.status,
            created_at=order.created_at,
        ))
    return references, total


def temporary_work_order_price_reference(
    session: Session,
    work_order_id: int,
) -> TemporaryWorkOrderPriceReference | None:
    row = session.execute(
        select(WorkOrder, ProductionItem)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            WorkOrder.id == work_order_id,
            WorkOrder.is_temporary.is_(True),
            WorkOrder.work_order_type.in_(list(STANDARD_EXECUTION_WORK_ORDER_TYPES)),
        )
    ).one_or_none()
    if row is None:
        return None
    order, production_item = row
    if order.work_order_no is None or order.procedure_id is None:
        raise DomainError(
            "temporary_work_order_price_context_invalid",
            "临时工单计价信息不完整",
            status_code=409,
        )
    return TemporaryWorkOrderPriceReference(
        id=order.id,
        work_order_no=order.work_order_no,
        product_id=production_item.product_id,
        product_version=production_item.product_version,
        origin_flow_node_id=production_item.origin_flow_node_id,
        flow_node_id=order.flow_node_id,
        procedure_id=order.procedure_id,
        status=order.status,
        created_at=order.created_at,
    )


def part_production_references(
    session: Session,
    identities: Collection[PartProductionIdentity],
) -> dict[PartProductionIdentity, PartProductionReference]:
    if not identities:
        return {}
    rows = session.scalars(
        select(ProductionItem).where(
            tuple_(
                ProductionItem.customer_order_item_id,
                ProductionItem.product_id,
                ProductionItem.product_version,
                ProductionItem.product_bom_id,
                ProductionItem.origin_flow_node_id,
            ).in_(list(identities)),
            ProductionItem.product_bom_id.is_not(None),
        )
    )
    references: dict[PartProductionIdentity, PartProductionReference] = {}
    for item in rows:
        if item.product_bom_id is None:
            continue
        identity = (
            item.customer_order_item_id,
            item.product_id,
            item.product_version,
            item.product_bom_id,
            item.origin_flow_node_id,
        )
        references[identity] = PartProductionReference(
            id=item.id,
            customer_order_item_id=item.customer_order_item_id,
            product_id=item.product_id,
            product_version=item.product_version,
            product_bom_id=item.product_bom_id,
            origin_flow_node_id=item.origin_flow_node_id,
        )
    return references


def supplier_processing_work_order_references(
    session: Session,
    positions: Collection[SupplierProcessingPosition],
) -> dict[SupplierProcessingPosition, SupplierProcessingWorkOrderReference]:
    if not positions:
        return {}
    rows = session.scalars(
        select(WorkOrder).where(
            tuple_(WorkOrder.production_item_id, WorkOrder.flow_node_id).in_(
                list(positions)
            ),
            WorkOrder.work_order_type == WORK_ORDER_SUPPLIER_PROCESSING,
            WorkOrder.status != "cancelled",
        )
    )
    return {
        (
            order.production_item_id,
            order.flow_node_id,
        ): SupplierProcessingWorkOrderReference(
            id=order.id,
            production_item_id=order.production_item_id,
            flow_node_id=order.flow_node_id,
            status=order.status,
        )
        for order in rows
    }


def supplier_processing_qc_order_references(
    session: Session,
    work_order_ids: Collection[int] | None = None,
    *,
    history: bool = False,
) -> dict[int, SupplierProcessingQcOrderReference]:
    if work_order_ids is not None and not work_order_ids:
        return {}
    status_condition = (
        WorkOrder.status == "closed"
        if history
        else WorkOrder.status == WORK_ORDER_STATUS_OPEN
    )
    statement = select(WorkOrder).where(
        WorkOrder.work_order_type == WORK_ORDER_SUPPLIER_PROCESSING,
        status_condition,
    )
    if work_order_ids is not None:
        statement = statement.where(WorkOrder.id.in_(list(work_order_ids)))
    orders = list(session.scalars(
        statement.order_by(
            WorkOrder.created_at.desc(),
            WorkOrder.id.desc(),
        )
    ))
    if not orders:
        return {}
    order_ids = [order.id for order in orders]
    batches_by_order: dict[int, list[WorkOrderBatch]] = {}
    for batch in session.scalars(
        select(WorkOrderBatch)
        .where(WorkOrderBatch.work_order_id.in_(order_ids))
        .order_by(WorkOrderBatch.work_order_id, WorkOrderBatch.id)
    ):
        batches_by_order.setdefault(batch.work_order_id, []).append(batch)
    result: dict[int, SupplierProcessingQcOrderReference] = {}
    for order in orders:
        if (
            not order.work_order_no
            or not order.source_flow_node_id
            or not order.supplier_name
            or not order.supplier_process_name
        ):
            raise DomainError(
                "supplier_processing_work_order_context_invalid",
                "委外加工工单执行快照不完整",
                status_code=409,
            )
        batch_rows = tuple(batches_by_order.get(order.id, ()))
        progress = calculate_supplier_processing_qc_progress(order, batch_rows)
        validate_supplier_processing_work_order_progress(order, progress)
        if any(
            batch.qc_worker_id is None or batch.qc_worker_name is None
            for batch in batch_rows
        ):
            raise DomainError(
                "supplier_processing_qc_batch_invalid",
                "委外加工工单存在不符合分次质检规则的批次",
                status_code=409,
            )
        batches = tuple(
            SupplierProcessingQcBatchReference(
                id=batch.id,
                work_order_id=batch.work_order_id,
                submitted_quantity=batch.submitted_quantity,
                source_flow_node_id=batch.source_flow_node_id,
                qualified_quantity=batch.qualified_quantity,
                rework_quantity=batch.rework_quantity,
                scrap_quantity=batch.scrap_quantity,
                lost_quantity=batch.lost_quantity,
                qc_worker_id=batch.qc_worker_id,
                qc_worker_name=batch.qc_worker_name,
                defect_reason=batch.defect_reason,
                qualified_destination=batch.qualified_destination,
                destination_decided_at=batch.destination_decided_at,
                destination_decided_by=batch.destination_decided_by,
                recorded_at=batch.recorded_at,
            )
            for batch in batch_rows
        )
        reference = SupplierProcessingQcOrderReference(
            id=order.id,
            work_order_no=order.work_order_no,
            production_item_id=order.production_item_id,
            flow_node_id=order.flow_node_id,
            source_flow_node_id=order.source_flow_node_id,
            supplier_name=order.supplier_name,
            supplier_process_name=order.supplier_process_name,
            remark=order.remark,
            quantity=order.quantity,
            status=order.status,
            created_at=order.created_at,
            batches=batches,
            qc_progress=progress,
        )
        result[order.id] = reference
    return result


def reserved_repository_quantities(
    session: Session,
    repository_ids: Collection[int],
) -> dict[int, int]:
    return reserved_quantities(session, list(repository_ids))


def has_product_version_production_reference(
    session: Session,
    product_id: int,
    product_version: int,
) -> bool:
    return bool(
        session.scalar(
            select(ProductionItem.id)
            .where(
                ProductionItem.product_id == product_id,
                ProductionItem.product_version == product_version,
            )
            .limit(1)
        )
    )


def list_standard_execution_config_keys(
    session: Session,
    product_ids: Collection[int],
    procedure_ids: Collection[int],
) -> set[tuple[int, int, str, str, int]]:
    if not product_ids or not procedure_ids:
        return set()
    return set(
        session.execute(
            select(
                ProductionItem.product_id,
                ProductionItem.product_version,
                ProductionItem.origin_flow_node_id,
                WorkOrder.flow_node_id,
                WorkOrder.procedure_id,
            )
            .join(WorkOrder, WorkOrder.production_item_id == ProductionItem.id)
            .where(
                ProductionItem.product_id.in_(product_ids),
                WorkOrder.procedure_id.in_(procedure_ids),
            )
        ).all()
    )


def has_standard_execution_order(
    session: Session,
    *,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    procedure_id: int,
) -> bool:
    return session.scalar(
        select(WorkOrder.id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            ProductionItem.product_id == product_id,
            ProductionItem.product_version == product_version,
            ProductionItem.origin_flow_node_id == origin_flow_node_id,
            WorkOrder.flow_node_id == flow_node_id,
            WorkOrder.procedure_id == procedure_id,
        )
        .limit(1)
    ) is not None


def list_standard_execution_order_ids(
    session: Session,
    *,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
) -> list[int]:
    return list(session.scalars(
        select(WorkOrder.id)
        .join(ProductionItem, ProductionItem.id == WorkOrder.production_item_id)
        .where(
            ProductionItem.product_id == product_id,
            ProductionItem.product_version == product_version,
            ProductionItem.origin_flow_node_id == origin_flow_node_id,
            WorkOrder.flow_node_id == flow_node_id,
        )
        .order_by(WorkOrder.id)
    ))


def has_work_order_for_procedure(session: Session, procedure_id: int) -> bool:
    return session.scalar(
        select(WorkOrder.id)
        .where(WorkOrder.procedure_id == procedure_id)
        .limit(1)
    ) is not None


__all__ = [
    "PartProductionIdentity",
    "PartProductionReference",
    "SupplierProcessingPosition",
    "SupplierProcessingQcBatchReference",
    "SupplierProcessingQcOrderReference",
    "SupplierProcessingWorkOrderReference",
    "TemporaryWorkOrderPriceReference",
    "has_product_version_production_reference",
    "has_standard_execution_order",
    "has_work_order_for_procedure",
    "list_standard_execution_order_ids",
    "list_standard_execution_config_keys",
    "part_production_references",
    "reserved_repository_quantities",
    "supplier_processing_work_order_references",
    "supplier_processing_qc_order_references",
    "temporary_work_order_price_reference",
    "temporary_work_order_price_references",
]
