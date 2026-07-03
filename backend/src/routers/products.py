from fastapi import APIRouter, HTTPException

from models.production import Product

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products(department: str | None = None):
    resolved_department = department.strip() if department and department.strip() else None
    return {"data": Product.list_all(department=resolved_department)}


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
