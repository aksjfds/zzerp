from fastapi import APIRouter, Depends, HTTPException

from models.production import Product
from schemas.production import CreateProductPayload
from security import require_any_permission

router = APIRouter(prefix="/products", tags=["products"])


def normalize_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name}不能为空")
    return normalized


@router.get("")
def list_products():
    return {"data": Product.list_all()}


@router.get("/{product_id}/departments/{department}/progress")
def get_department_progress(product_id: int, department: str):
    try:
        data = Product.department_progress(
            product_id=product_id,
            department=department.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"data": data}


@router.post("")
def create_product(
    payload: CreateProductPayload,
    user: dict = Depends(require_any_permission("product:add", csrf=True)),
):
    if user["department"] != "sys":
        raise HTTPException(status_code=403, detail="只有 admin 可以新增产品")

    try:
        process = [department.strip() for department in payload.process if department.strip()]
        product = Product.create(
            order_id=normalize_text(payload.order_id, "订单号"),
            zz_code=normalize_text(payload.zz_code, "本厂编码"),
            product_name=normalize_text(payload.product_name, "产品名称"),
            delivery_date=payload.delivery_date,
            process=process,
            quantity=payload.quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"data": product}
