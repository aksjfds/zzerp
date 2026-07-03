from fastapi import APIRouter, Depends, HTTPException, Response

from schemas.catalog import (
    MaterialCreate,
    MaterialSummary,
    MaterialUpdate,
    ProductCreate,
    ProductCustomerCodeCreate,
    ProductCustomerCodeUpdate,
    ProductDetail,
    ProductUpdate,
)
from security import require_any_permission
from services.catalog import CatalogService

router = APIRouter(prefix="/v2/engineering", tags=["v2-engineering"])


@router.get("/products", response_model=list[ProductDetail])
def list_products(
    keyword: str | None = None,
    _: dict = Depends(require_any_permission("product:view", "product:manage")),
):
    return CatalogService.list_products(keyword)


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(
    product_id: int,
    _: dict = Depends(require_any_permission("product:view", "product:manage")),
):
    try:
        return CatalogService.get_product(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/products", response_model=ProductDetail)
def create_product(
    payload: ProductCreate,
    user: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return CatalogService.create_product(payload, created_by=user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/products/{product_id}", response_model=ProductDetail)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    if payload.product_name is None:
        raise HTTPException(status_code=400, detail="没有需要修改的产品字段")
    try:
        return CatalogService.update_product_name(product_id, payload.product_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/products/{product_id}/publish", response_model=ProductDetail)
def publish_product(
    product_id: int,
    user: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return CatalogService.publish_product(product_id, published_by=user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/products/{product_id}/deactivate", response_model=ProductDetail)
def deactivate_product(
    product_id: int,
    _: dict = Depends(require_any_permission("product:manage", csrf=True)),
):
    try:
        return CatalogService.deactivate_product(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/products/{product_id}/customer-codes",
    response_model=ProductDetail,
)
def add_customer_code(
    product_id: int,
    payload: ProductCustomerCodeCreate,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return CatalogService.add_customer_code(product_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/customer-codes/{customer_code_id}",
    response_model=ProductDetail,
)
def update_customer_code(
    customer_code_id: int,
    payload: ProductCustomerCodeUpdate,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return CatalogService.update_customer_code(
            customer_code_id=customer_code_id,
            treatment_ids=payload.treatment_ids,
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/products/{product_id}/materials",
    response_model=MaterialSummary,
)
def add_material(
    product_id: int,
    payload: MaterialCreate,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return CatalogService.add_material(product_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/materials/{material_id}", response_model=MaterialSummary)
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return CatalogService.update_material(
            material_id=material_id,
            material_code=payload.material_code,
            material_type=payload.material_type,
            material_name=payload.material_name,
            material_grade=payload.material_grade,
            specification=payload.specification,
            note=payload.note,
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/materials/{material_id}", status_code=204)
def delete_unused_material(
    material_id: int,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        CatalogService.delete_unused_material(material_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)
