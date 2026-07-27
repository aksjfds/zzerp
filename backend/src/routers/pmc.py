from fastapi import APIRouter, Depends, HTTPException, Query

from authorization import require_any_permission
from domain.permissions import PRODUCTION_VIEW
from modules.planning.api import list_part_progress


router = APIRouter(prefix="/pmc", tags=["pmc"])


@router.get("/part-production-progress")
def part_production_progress(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    keyword: str | None = Query(default=None, max_length=200),
    order_status: str | None = Query(default=None, max_length=30),
    department_code: str | None = Query(default=None, max_length=50),
    only_exception: bool = Query(default=False),
    only_unfinished: bool = Query(default=False),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", "pmc"}:
        raise HTTPException(status_code=403, detail="只有PMC可以查看配件生产进度")
    data, total, departments = list_part_progress(
        page,
        page_size,
        keyword,
        order_status,
        department_code,
        only_exception,
        only_unfinished,
    )
    return {"data": data, "total": total, "departments": departments}
