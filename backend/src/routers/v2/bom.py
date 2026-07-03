from fastapi import APIRouter, Depends, HTTPException, Response

from schemas.bom import (
    ProductBomVersionData,
    ProductBomVersionInput,
    ProductionStructureData,
    SemiFinishedVersionData,
    SemiFinishedVersionInput,
)
from security import require_any_permission
from services.bom import BomService

router = APIRouter(prefix="/v2/engineering", tags=["v2-bom"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/products/{product_id}/bom-versions",
    response_model=list[ProductBomVersionData],
)
def list_bom_versions(
    product_id: int,
    _: dict = Depends(require_any_permission("product:view", "product:manage")),
):
    try:
        return BomService.list_bom_versions(product_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/products/{product_id}/bom-versions",
    response_model=ProductBomVersionData,
)
def create_bom_version(
    product_id: int,
    payload: ProductBomVersionInput,
    user: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return BomService.create_bom_version(product_id, payload, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.put("/bom-versions/{version_id}", response_model=ProductBomVersionData)
def update_bom_version(
    version_id: int,
    payload: ProductBomVersionInput,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return BomService.update_bom_version(version_id, payload)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/bom-versions/{version_id}/publish",
    response_model=ProductBomVersionData,
)
def publish_bom_version(
    version_id: int,
    user: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return BomService.publish_bom_version(version_id, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.delete("/bom-versions/{version_id}", status_code=204)
def delete_bom_version(
    version_id: int,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        BomService.delete_bom_version(version_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return Response(status_code=204)


@router.get(
    "/products/{product_id}/semi-finished-versions",
    response_model=list[SemiFinishedVersionData],
)
def list_semi_versions(
    product_id: int,
    _: dict = Depends(require_any_permission("product:view", "product:manage")),
):
    try:
        return BomService.list_semi_versions(product_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/materials/{material_id}/semi-finished-versions",
    response_model=SemiFinishedVersionData,
)
def create_semi_version(
    material_id: int,
    payload: SemiFinishedVersionInput,
    user: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return BomService.create_semi_version(material_id, payload, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.put(
    "/semi-finished-versions/{version_id}",
    response_model=SemiFinishedVersionData,
)
def update_semi_version(
    version_id: int,
    payload: SemiFinishedVersionInput,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return BomService.update_semi_version(version_id, payload)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/semi-finished-versions/{version_id}/publish",
    response_model=SemiFinishedVersionData,
)
def publish_semi_version(
    version_id: int,
    user: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        return BomService.publish_semi_version(version_id, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.delete("/semi-finished-versions/{version_id}", status_code=204)
def delete_semi_version(
    version_id: int,
    _: dict = Depends(
        require_any_permission("product:edit", "product:manage", csrf=True)
    ),
):
    try:
        BomService.delete_semi_version(version_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return Response(status_code=204)


@router.get(
    "/products/{product_id}/production-structure",
    response_model=ProductionStructureData,
)
def get_production_structure(
    product_id: int,
    _: dict = Depends(require_any_permission("product:view", "product:manage")),
):
    try:
        return BomService.production_structure(product_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
