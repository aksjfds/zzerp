from fastapi import APIRouter

from backend.src.models.production import Record

router = APIRouter(prefix="/records", tags=["records"])


@router.get("")
def list_records(zz_code: str, product: str):
    return {
        "data": Record.list_by_product(
            zz_code=zz_code.strip(),
            product=product.strip(),
        )
    }
