"""Unmounted routers for the staged core-business rewrite."""

from fastapi import APIRouter

from routers.v2 import (
    bom,
    customer_orders,
    engineering,
    master_data,
    production_plans,
    routing,
)


router = APIRouter()
router.include_router(master_data.router)
router.include_router(engineering.router)
router.include_router(bom.router)
router.include_router(routing.router)
router.include_router(customer_orders.router)
router.include_router(production_plans.router)
