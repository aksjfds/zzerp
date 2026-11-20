"""Explicit effective-record queries; audit and UUID lookups use plain select."""

from sqlalchemy import select
from sqlalchemy.orm import with_loader_criteria

from modules.errors import DomainError
from modules.planning.persistence import (
    DepartmentHandoffTicket,
    DepartmentWorkOrderMovement,
    OutsourceDispatch,
    OutsourceReturn,
    PurchaseOrder,
    PurchaseReceipt,
    QcInspection,
    QcReworkEvent,
    QcReworkTicket,
    WarehouseAllocation,
    WarehouseLot,
    WarehousePick,
)

OPERATION_MODELS = {'movement': DepartmentWorkOrderMovement, 'inspection': QcInspection,
                    'rework': QcReworkEvent, 'warehouse': WarehousePick,
                    'outsource': OutsourceDispatch, 'outsource_return': OutsourceReturn,
                    'purchase': PurchaseOrder, 'purchase_receipt': PurchaseReceipt}
REVOCABLE_MODELS = tuple(OPERATION_MODELS.values())


def select_current(*entities):
    criteria = [with_loader_criteria(model, lambda entity: entity.revoked_at.is_(None), include_aliases=True)
                for model in REVOCABLE_MODELS]
    criteria.extend((
        with_loader_criteria(DepartmentHandoffTicket, select(DepartmentWorkOrderMovement.id).where(
            DepartmentWorkOrderMovement.id == DepartmentHandoffTicket.issue_movement_id,
            DepartmentWorkOrderMovement.revoked_at.is_(None)).correlate_except(DepartmentWorkOrderMovement).exists(), include_aliases=True),
        with_loader_criteria(QcReworkTicket, select(QcInspection.id).where(
            QcInspection.id == QcReworkTicket.inspection_id, QcInspection.revoked_at.is_(None)).correlate_except(QcInspection).exists(), include_aliases=True),
        with_loader_criteria(WarehouseLot, select(DepartmentWorkOrderMovement.id).where(
            DepartmentWorkOrderMovement.id == WarehouseLot.receipt_movement_id,
            DepartmentWorkOrderMovement.revoked_at.is_(None)).correlate_except(DepartmentWorkOrderMovement).exists(), include_aliases=True),
        with_loader_criteria(WarehouseAllocation, select(WarehousePick.id).where(
            WarehousePick.id == WarehouseAllocation.pick_id, WarehousePick.revoked_at.is_(None)).correlate_except(WarehousePick).exists(), include_aliases=True),
    ))
    return select(*entities).options(*criteria)


def require_effective(record):
    if record is not None and record.revoked_at is not None:
        raise DomainError('operation_revoked', '原操作已撤回，请刷新后重新登记，不能复用原提交标识', status_code=409)
