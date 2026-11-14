from fastapi import APIRouter, Depends, Query

from zzerp.database import Database
from zzerp.http.authorization import require_any_permission
from zzerp.http.dependencies import get_database
from zzerp.modules.identity.contracts import PLAN_VIEW, PRODUCT_VIEW, UserResponse
from zzerp.modules.sales.api import list_customers
from zzerp.modules.sales.contracts import CustomerListEnvelope

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListEnvelope)
def customer_list(
    keyword: str | None = Query(default=None, max_length=200),
    _user: UserResponse = Depends(require_any_permission(PRODUCT_VIEW, PLAN_VIEW)),
    database: Database = Depends(get_database),
):
    return {"data": database.query(list_customers, keyword)}
