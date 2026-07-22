from fastapi import APIRouter, Depends, Query

from authorization import require_any_permission
from domain.permissions import ORDER_VIEW, PRODUCT_VIEW
from schemas.customers import CustomerListEnvelope
from services.customers import list_customers


router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListEnvelope)
def customer_list(
    keyword: str | None = Query(default=None, max_length=200),
    _user: dict = Depends(require_any_permission(PRODUCT_VIEW, ORDER_VIEW)),
):
    return {"data": list_customers(keyword)}
