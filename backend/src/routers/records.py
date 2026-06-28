from fastapi import APIRouter, Depends

from models.production import Record
from security import ensure_department_access, require_any_permission

router = APIRouter(prefix="/records", tags=["records"])


@router.get("")
def list_records(
    order_id: str,
    zz_code: str,
    product: str,
    department: str | None = None,
    user: dict = Depends(require_any_permission("record:view")),
):
    if user["department"] != "sys":
        ensure_department_access(user, department or "")

    return {
        "data": Record.list_by_product(
            order_id=order_id.strip(),
            zz_code=zz_code.strip(),
            product=product.strip(),
            department=department.strip() if department else None,
        )
    }
