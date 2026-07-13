from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from authorization import require_any_permission
from domain.permissions import PRODUCTION_VIEW
from schemas.production import (
    RepositoryListEnvelope,
    WorkerListEnvelope,
)
from services.production_cards import list_production_cards
from services.work_order_queries import list_department_workers


router = APIRouter(tags=["production"])


@router.get(
    "/departments/{department_code}/repositories",
    response_model=RepositoryListEnvelope,
)
def department_repositories(
    department_code: str,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=10000),
    keyword: str | None = Query(default=None, max_length=200),
    arrived_from: date | None = None,
    arrived_to: date | None = None,
    work_status: str = Query(default="all", pattern="^(all|unprocessed|processing|completed)$"),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", department_code}:
        raise HTTPException(status_code=403, detail="无权访问该部门")
    if arrived_from and arrived_to and arrived_from > arrived_to:
        raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期")
    data, total = list_production_cards(
        department_code, page, page_size, keyword, arrived_from, arrived_to, work_status
    )
    return {"data": data, "total": total}


@router.get(
    "/departments/{department_code}/workers",
    response_model=WorkerListEnvelope,
)
def department_workers(
    department_code: str,
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", department_code}:
        raise HTTPException(status_code=403, detail="无权访问该部门")
    return {"data": list_department_workers(department_code)}
