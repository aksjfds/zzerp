from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from authorization import require_any_permission
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW
from schemas.production import (
    ProcedureDispatchCreate,
    ProcedureDispatchEnvelope,
    RepositoryListEnvelope,
    TagCardListEnvelope,
    WorkerListEnvelope,
)
from services.procedure_dispatches import dispatch_tag_stock
from services.production_card_listing import list_production_cards
from services.production_tag_cards import list_tag_cards
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


@router.get(
    "/departments/{department_code}/production-items/{production_item_id}/tag-cards",
    response_model=TagCardListEnvelope,
)
def production_item_tag_cards(
    department_code: str,
    production_item_id: int,
    flow_node_id: str = Query(min_length=1, max_length=200),
    source_flow_node_id: str = Query(min_length=1, max_length=200),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", department_code}:
        raise HTTPException(status_code=403, detail="无权访问该部门")
    return {
        "data": list_tag_cards(
            department_code,
            production_item_id,
            flow_node_id,
            source_flow_node_id,
        )
    }


@router.post(
    "/procedure-tag-stocks/{tag_stock_id}/dispatches",
    response_model=ProcedureDispatchEnvelope,
)
def procedure_tag_stock_dispatch(
    tag_stock_id: int,
    payload: ProcedureDispatchCreate,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    return {
        "data": dispatch_tag_stock(
            tag_stock_id,
            payload.quantity,
            user["department"],
        )
    }
