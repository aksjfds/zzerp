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
def list_products(
    user: dict = Depends(require_any_permission("product:view", "task:view")),
):
    department = None if user["department"] == "sys" else user["department"]
    return {"data": Product.list_all(department=department)}


@router.post("")
def create_product(
    payload: CreateProductPayload,
    _user: dict = Depends(require_any_permission("product:add", csrf=True)),
):
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
