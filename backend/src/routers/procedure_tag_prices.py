from fastapi import APIRouter, Depends, Query, Response

from authorization import require_any_permission
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW
from schemas.procedure_tag_prices import (
    ProcedureTagPriceListEnvelope,
    ProcedureTagPriceUpdate,
)
from modules.standard_execution.api import (
    list_procedure_tag_prices,
    update_procedure_tag_prices,
)


router = APIRouter(tags=["procedure-tag-prices"])


@router.get(
    "/departments/{department_code}/procedure-tag-prices",
    response_model=ProcedureTagPriceListEnvelope,
)
def procedure_tag_prices(
    department_code: str,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=20, gt=0, le=100),
    keyword: str | None = Query(default=None, max_length=200),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    data, total = list_procedure_tag_prices(
        department_code,
        page,
        page_size,
        keyword,
        user["department"],
    )
    return {"data": data, "total": total}


@router.put(
    "/departments/{department_code}/procedure-tag-prices/{product_id}/{product_version}/{origin_flow_node_id}/{procedure_id}",
    status_code=204,
)
def procedure_tag_price_update(
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    procedure_id: int,
    payload: ProcedureTagPriceUpdate,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    update_procedure_tag_prices(
        department_code,
        product_id,
        product_version,
        origin_flow_node_id,
        procedure_id,
        payload,
        user["department"],
    )
    return Response(status_code=204)
