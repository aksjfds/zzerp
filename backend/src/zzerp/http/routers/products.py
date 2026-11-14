from fastapi import APIRouter, Depends, Query, status

from zzerp.application.engineering import (
    get_product,
    replace_product_bom,
    save_product_appearance,
    save_product_process_flow_draft,
    update_product_info,
    update_product_process_flow,
)
from zzerp.database import Database
from zzerp.http.authorization import require_any_permission
from zzerp.http.dependencies import get_database
from zzerp.modules.engineering.api import (
    create_product,
    list_product_appearances,
    list_product_options,
    list_products,
)
from zzerp.modules.engineering.contracts import (
    AppearancePayload,
    CreateProductPayload,
    ProductAppearancesEnvelope,
    ProductDetailEnvelope,
    ProductListEnvelope,
    ProductOptionsEnvelope,
    ReplaceBomPayload,
    UpdateProcessFlowPayload,
    UpdateProductPayload,
)
from zzerp.modules.identity.contracts import PRODUCT_ADD, PRODUCT_EDIT, PRODUCT_VIEW, UserResponse

router = APIRouter(prefix="/products", tags=["engineering-products"])


@router.get("", response_model=ProductListEnvelope)
def product_list(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0, le=200),
    keyword: str | None = Query(default=None, max_length=200),
    customer_id: int | None = Query(default=None, gt=0),
    _user: UserResponse = Depends(require_any_permission(PRODUCT_VIEW)),
    database: Database = Depends(get_database),
):
    data, total = database.query(list_products, page, page_size, keyword, customer_id)
    return {"data": data, "total": total}


@router.get("/options", response_model=ProductOptionsEnvelope)
def product_options(
    customer_id: int = Query(gt=0),
    keyword: str | None = Query(default=None, max_length=200),
    _user: UserResponse = Depends(require_any_permission(PRODUCT_VIEW)),
    database: Database = Depends(get_database),
):
    return {"data": database.query(list_product_options, customer_id, keyword)}


@router.get("/{product_id}", response_model=ProductDetailEnvelope)
def product_detail(
    product_id: int,
    appearance_id: int | None = Query(default=None, gt=0),
    _user: UserResponse = Depends(require_any_permission(PRODUCT_VIEW)),
    database: Database = Depends(get_database),
):
    return {"data": database.query(get_product, product_id, appearance_id)}


@router.get("/{product_id}/appearances", response_model=ProductAppearancesEnvelope)
def product_appearances(
    product_id: int,
    _user: UserResponse = Depends(require_any_permission(PRODUCT_VIEW)),
    database: Database = Depends(get_database),
):
    return {"data": database.query(list_product_appearances, product_id)}


@router.post("/{product_id}/appearances", response_model=ProductDetailEnvelope)
def appearance_create(
    product_id: int,
    payload: AppearancePayload,
    _user: UserResponse = Depends(require_any_permission(PRODUCT_EDIT, csrf=True)),
    database: Database = Depends(get_database),
):
    return {"data": database.command(save_product_appearance, product_id, payload)}


@router.put("/{product_id}/appearances/{appearance_id}", response_model=ProductDetailEnvelope)
def appearance_update(
    product_id: int,
    appearance_id: int,
    payload: AppearancePayload,
    _user: UserResponse = Depends(require_any_permission(PRODUCT_EDIT, csrf=True)),
    database: Database = Depends(get_database),
):
    return {"data": database.command(save_product_appearance, product_id, payload, appearance_id)}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductDetailEnvelope,
)
def product_create(
    payload: CreateProductPayload,
    _user: UserResponse = Depends(require_any_permission(PRODUCT_ADD, csrf=True)),
    database: Database = Depends(get_database),
):
    return {"data": database.command(create_product, payload)}


@router.put("/{product_id}", response_model=ProductDetailEnvelope)
def product_update(
    product_id: int,
    payload: UpdateProductPayload,
    _user: UserResponse = Depends(require_any_permission(PRODUCT_EDIT, csrf=True)),
    database: Database = Depends(get_database),
):
    return {"data": database.command(update_product_info, product_id, payload)}


@router.put("/{product_id}/bom", response_model=ProductDetailEnvelope)
def product_bom_replace(
    product_id: int,
    payload: ReplaceBomPayload,
    _user: UserResponse = Depends(require_any_permission(PRODUCT_EDIT, csrf=True)),
    database: Database = Depends(get_database),
):
    return {
        "data": database.command(
            replace_product_bom,
            product_id,
            payload.expected_revision,
            payload.bom_items,
        )
    }


@router.put("/{product_id}/process-flow", response_model=ProductDetailEnvelope)
def product_process_flow_update(
    product_id: int,
    payload: UpdateProcessFlowPayload,
    _user: UserResponse = Depends(require_any_permission(PRODUCT_EDIT, csrf=True)),
    database: Database = Depends(get_database),
):
    return {
        "data": database.command(
            update_product_process_flow,
            product_id,
            payload.expected_revision,
            payload.appearance_id,
            payload.process_flow,
        )
    }


@router.put("/{product_id}/process-flow/draft", response_model=ProductDetailEnvelope)
def product_process_flow_draft_save(
    product_id: int,
    payload: UpdateProcessFlowPayload,
    _user: UserResponse = Depends(require_any_permission(PRODUCT_EDIT, csrf=True)),
    database: Database = Depends(get_database),
):
    return {
        "data": database.command(
            save_product_process_flow_draft,
            product_id,
            payload.expected_revision,
            payload.appearance_id,
            payload.process_flow,
        )
    }
