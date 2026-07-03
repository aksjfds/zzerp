from fastapi import APIRouter, Depends, HTTPException, Response

from schemas.routing import MaterialRouteData, MaterialRouteInput
from security import require_any_permission
from services.routing import RoutingService

router = APIRouter(prefix="/v2/engineering", tags=["v2-routing"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/products/{product_id}/material-routes",
    response_model=list[MaterialRouteData],
)
def list_material_routes(
    product_id: int,
    _: dict = Depends(
        require_any_permission("product:view", "route:edit", "product:manage")
    ),
):
    try:
        return RoutingService.list_routes(product_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/materials/{material_id}/route-versions",
    response_model=MaterialRouteData,
)
def create_material_route(
    material_id: int,
    payload: MaterialRouteInput,
    user: dict = Depends(
        require_any_permission("route:edit", "product:manage", csrf=True)
    ),
):
    try:
        return RoutingService.create_route(material_id, payload, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.put("/route-versions/{version_id}", response_model=MaterialRouteData)
def update_material_route(
    version_id: int,
    payload: MaterialRouteInput,
    _: dict = Depends(
        require_any_permission("route:edit", "product:manage", csrf=True)
    ),
):
    try:
        return RoutingService.update_route(version_id, payload)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post(
    "/route-versions/{version_id}/publish",
    response_model=MaterialRouteData,
)
def publish_material_route(
    version_id: int,
    user: dict = Depends(
        require_any_permission("route:edit", "product:manage", csrf=True)
    ),
):
    try:
        return RoutingService.publish_route(version_id, user["id"])
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.delete("/route-versions/{version_id}", status_code=204)
def delete_material_route(
    version_id: int,
    _: dict = Depends(
        require_any_permission("route:edit", "product:manage", csrf=True)
    ),
):
    try:
        RoutingService.delete_route(version_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return Response(status_code=204)
