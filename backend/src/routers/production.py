from fastapi import APIRouter, Depends, HTTPException

from authorization import require_any_permission
from domain.permissions import PRODUCTION_VIEW
from schemas.production import RepositoryListEnvelope
from services.production_repositories import list_department_repositories


router = APIRouter(tags=["production"])


@router.get(
    "/departments/{department_code}/repositories",
    response_model=RepositoryListEnvelope,
)
def department_repositories(
    department_code: str,
    user: dict = Depends(require_any_permission(PRODUCTION_VIEW)),
):
    if user["department"] not in {"sys", department_code}:
        raise HTTPException(status_code=403, detail="无权访问该部门")
    return {"data": list_department_repositories(department_code)}
