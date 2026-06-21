from fastapi import APIRouter, HTTPException

from models.production import Product
from schemas.production import CreateProductPayload

router = APIRouter(prefix="/products", tags=["products"])


def normalize_text(value: str) -> str:
    return value.strip()


@router.get("")
def list_products():
    return {"data": Product.list_all()}


@router.post("")
def create_product(payload: CreateProductPayload):
    process = [department.strip() for department in payload.process if department.strip()]

    try:
        product = Product.create(
            zz_code=normalize_text(payload.zz_code),
            product_name=normalize_text(payload.product_name),
            process=process,
            quantity=payload.quantity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"data": product}
