from fastapi import APIRouter, Depends, Query, Response

from authorization import require_any_permission
from domain.permissions import PRODUCTION_MANAGE, PRODUCTION_VIEW
from modules.standard_execution.api import (
    confirm_procedure_configuration,
    list_procedure_prices,
    update_procedure_price,
)
from schemas.procedure_prices import ProcedurePriceListEnvelope, ProcedurePriceUpdate


router = APIRouter(tags=["procedure-prices"])


@router.get(
    "/departments/{department_code}/procedure-prices",
    response_model=ProcedurePriceListEnvelope,
)
def procedure_prices(
    department_code: str,
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=20, gt=0, le=100),
    keyword: str | None = Query(default=None, max_length=200),
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    data, total = list_procedure_prices(
        department_code,
        page,
        page_size,
        keyword,
        user["department"],
        user["is_system"],
    )
    return {"data": data, "total": total}


@router.put(
    "/departments/{department_code}/procedure-prices/"
    "{product_id}/{product_version}/{origin_flow_node_id}/{flow_node_id}",
    status_code=204,
)
def procedure_price_update(
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    payload: ProcedurePriceUpdate,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    update_procedure_price(
        department_code,
        product_id,
        product_version,
        origin_flow_node_id,
        flow_node_id,
        payload,
        user["department"],
        user["is_system"],
        user["username"],
    )
    return Response(status_code=204)


@router.post(
    "/departments/{department_code}/procedure-prices/"
    "{product_id}/{product_version}/{origin_flow_node_id}/{flow_node_id}/confirm",
    status_code=204,
)
def procedure_configuration_confirm(
    department_code: str,
    product_id: int,
    product_version: int,
    origin_flow_node_id: str,
    flow_node_id: str,
    payload: ProcedurePriceUpdate,
    user: dict = Depends(require_any_permission(PRODUCTION_MANAGE, csrf=True)),
):
    confirm_procedure_configuration(
        department_code,
        product_id,
        product_version,
        origin_flow_node_id,
        flow_node_id,
        payload,
        user["department"],
        user["is_system"],
        user["username"],
    )
    return Response(status_code=204)
