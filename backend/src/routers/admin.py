from fastapi import APIRouter, Depends, Query

from authorization import require_any_permission
from domain.permissions import PRODUCTION_VIEW
from schemas.admin import (
    AdminWorkerHistoryEnvelope,
    AdminWorkerOverviewEnvelope,
    AdminWorkerPayEnvelope,
)
from modules.workforce.api import worker_history, worker_overview, worker_pay_summary


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/workers/overview", response_model=AdminWorkerOverviewEnvelope)
def admin_worker_overview(
    _user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    return {"data": worker_overview()}


@router.get("/workers/{worker_id}/work-history", response_model=AdminWorkerHistoryEnvelope)
def admin_worker_history(
    worker_id: int,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    _user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    return {"data": worker_history(worker_id, month)}


@router.get("/workers/{worker_id}/pay", response_model=AdminWorkerPayEnvelope)
def admin_worker_pay(
    worker_id: int,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    _user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    return {"data": worker_pay_summary(worker_id, month)}
