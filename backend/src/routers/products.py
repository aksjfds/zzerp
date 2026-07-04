from fastapi import APIRouter, Depends, Query, Response, status

from authorization import require_any_permission
from domain.permissions import PRODUCT_ADD, PRODUCT_DELETE, PRODUCT_EDIT, PRODUCT_VIEW
from schemas.engineering import (
    CreateProductPayload,
    ProductDetailEnvelope,
    ProductListEnvelope,
    ReplaceBomPayload,
    UpdateProcessFlowPayload,
    UpdateProductPayload,
)
from services.engineering_product_commands import (
    create_product,
    delete_product,
    replace_product_bom,
    update_product_info,
    update_product_process_flow,
)
from services.engineering_product_queries import get_product, list_products


router = APIRouter(prefix="/products", tags=["engineering-products"])


@router.get("", response_model=ProductListEnvelope)
def product_list(
    _user: dict = Depends(require_any_permission(PRODUCT_VIEW)),
):
    return {"data": list_products()}


@router.get("/{product_id}", response_model=ProductDetailEnvelope)
def product_detail(
    product_id: int,
    _user: dict = Depends(require_any_permission(PRODUCT_VIEW)),
):
    return {"data": get_product(product_id)}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductDetailEnvelope,
)
def product_create(
    payload: CreateProductPayload,
    _user: dict = Depends(require_any_permission(PRODUCT_ADD, csrf=True)),
):
    return {"data": create_product(payload)}


@router.put("/{product_id}", response_model=ProductDetailEnvelope)
def product_update(
    product_id: int,
    payload: UpdateProductPayload,
    _user: dict = Depends(require_any_permission(PRODUCT_EDIT, csrf=True)),
):
    return {"data": update_product_info(product_id, payload)}


@router.put("/{product_id}/bom", response_model=ProductDetailEnvelope)
def product_bom_replace(
    product_id: int,
    payload: ReplaceBomPayload,
    _user: dict = Depends(require_any_permission(PRODUCT_EDIT, csrf=True)),
):
    return {
        "data": replace_product_bom(
            product_id,
            payload.expected_version,
            payload.bom_items,
        )
    }


@router.put("/{product_id}/process-flow", response_model=ProductDetailEnvelope)
def product_process_flow_update(
    product_id: int,
    payload: UpdateProcessFlowPayload,
    _user: dict = Depends(require_any_permission(PRODUCT_EDIT, csrf=True)),
):
    return {
        "data": update_product_process_flow(
            product_id,
            payload.expected_version,
            payload.process_flow,
        )
    }


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def product_delete(
    product_id: int,
    expected_version: int = Query(gt=0),
    _user: dict = Depends(require_any_permission(PRODUCT_DELETE, csrf=True)),
):
    delete_product(product_id, expected_version)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
