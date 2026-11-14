"""Uvicorn factory: module imports are inert, resources belong to the application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from zzerp.config import Settings, load_settings
from zzerp.database import Database
from zzerp.http.errors import register_error_handlers
from zzerp.http.health import health, readiness, root
from zzerp.http.routers import auth, customers, production_departments, production_plans, products


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings if settings is not None else load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database.create(configured)
        app.state.database = database
        try:
            yield
        finally:
            database.close()

    app = FastAPI(title="zzerp", lifespan=lifespan)
    app.state.settings = configured
    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(configured.allowed_origins),
        allow_origin_regex=configured.allowed_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def validate_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and origin
            and not configured.allows_origin(origin)
        ):
            return JSONResponse(status_code=403, content={"detail": "请求来源不受信任"})
        return await call_next(request)

    for router in (
        auth.router,
        customers.router,
        products.router,
        production_plans.router,
        production_departments.router,
    ):
        app.include_router(router)
    app.add_api_route("/", root, methods=["GET"])
    app.add_api_route("/health", health, methods=["GET", "HEAD"], include_in_schema=False)
    app.add_api_route("/ready", readiness, methods=["GET"])
    return app
