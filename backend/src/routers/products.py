from typing import Annotated

from application.engineering import (
    create_product_version,
    get_product,
    replace_product_bom,
    save_product_process_flow_draft,
    update_product_info,
    update_product_process_flow,
)
from authorization import require_any_permission
from domain.permissions import PRODUCT_ADD, PRODUCT_EDIT, PRODUCT_VIEW
from fastapi import APIRouter, Depends, Query, status
from modules.engineering.api import create_product, list_product_versions, list_products
from schemas.engineering import (
    CreateProductPayload,
    ProductDetailEnvelope,
    ProductListEnvelope,
    ProductVersionsEnvelope,
    ReplaceBomPayload,
    UpdateProcessFlowPayload,
    UpdateProductPayload,
)

ProductViewer = Annotated[dict, Depends(require_any_permission(PRODUCT_VIEW))]
ProductCreator = Annotated[dict, Depends(require_any_permission(PRODUCT_ADD, csrf=True))]
ProductEditor = Annotated[dict, Depends(require_any_permission(PRODUCT_EDIT, csrf=True))]


router = APIRouter(prefix="/products", tags=["engineering-products"])


@router.get("", response_model=ProductListEnvelope)
def product_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    keyword: str | None = Query(default=None, max_length=200),
    customer_id: int | None = Query(default=None, gt=0),
    *, _user: ProductViewer,
):
    data, total = list_products(page, page_size, keyword, customer_id)
    return {"data": data, "total": total}


@router.get("/{product_id}", response_model=ProductDetailEnvelope)
def product_detail(
    product_id: int,
    version: int | None = Query(default=None, gt=0),
    *, _user: ProductViewer,
):
    return {"data": get_product(product_id, version)}


@router.get("/{product_id}/versions", response_model=ProductVersionsEnvelope)
def product_versions(
    product_id: int,
    *, _user: ProductViewer,
):
    return {"data": list_product_versions(product_id)}


@router.post("/{product_id}/versions", response_model=ProductDetailEnvelope)
def product_version_create(
    product_id: int,
    expected_revision: int = Query(gt=0),
    version_value: str = Query(min_length=1, max_length=100),
    source_version: int | None = Query(default=None, gt=0),
    *, _user: ProductEditor,
):
    return {"data": create_product_version(product_id, expected_revision, version_value, source_version)}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductDetailEnvelope,
)
def product_create(
    payload: CreateProductPayload,
    *, _user: ProductCreator,
):
    return {"data": create_product(payload)}


@router.put("/{product_id}", response_model=ProductDetailEnvelope)
def product_update(
    product_id: int,
    payload: UpdateProductPayload,
    *, _user: ProductEditor,
):
    return {"data": update_product_info(product_id, payload)}


@router.put("/{product_id}/bom", response_model=ProductDetailEnvelope)
def product_bom_replace(
    product_id: int,
    payload: ReplaceBomPayload,
    *, _user: ProductEditor,
):
    return {
        "data": replace_product_bom(
            product_id,
            payload.expected_revision,
            payload.product_version,
            payload.bom_items,
        )
    }


@router.put("/{product_id}/process-flow", response_model=ProductDetailEnvelope)
def product_process_flow_update(
    product_id: int,
    payload: UpdateProcessFlowPayload,
    *, _user: ProductEditor,
):
    return {
        "data": update_product_process_flow(
            product_id,
            payload.expected_revision,
            payload.product_version,
            payload.process_flow,
        )
    }


@router.put("/{product_id}/process-flow/draft", response_model=ProductDetailEnvelope)
def product_process_flow_draft_save(
    product_id: int,
    payload: UpdateProcessFlowPayload,
    *, _user: ProductEditor,
):
    return {
        "data": save_product_process_flow_draft(
            product_id,
            payload.expected_revision,
            payload.product_version,
            payload.process_flow,
        )
    }
