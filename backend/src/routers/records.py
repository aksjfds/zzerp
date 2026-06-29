from fastapi import APIRouter

from models.production import Record

router = APIRouter(prefix="/records", tags=["records"])


@router.get("")
def list_records(
    order_id: str,
    zz_code: str,
    product: str,
    department: str | None = None,
):
    return {
        "data": Record.list_by_product(
            order_id=order_id.strip(),
            zz_code=zz_code.strip(),
            product_name=product.strip(),
            department=department.strip() if department else None,
        )
    }
