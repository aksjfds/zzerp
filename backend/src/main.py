import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from config import get_settings
from domain.errors import DomainViolation
from routers import (
    admin,
    auth,
    customer_orders,
    customers,
    organization,
    pmc,
    procedure_tag_prices,
    production,
    products,
    qc,
    work_orders,
)
from services.errors import DomainError

app = FastAPI(title="zzerp")
settings = get_settings()
logger = logging.getLogger(__name__)


@app.exception_handler(DomainError)
async def handle_domain_error(_request: Request, exc: DomainError):
    detail = {"code": exc.code, "message": exc.message}
    if exc.path:
        detail["path"] = exc.path
    if exc.element_id:
        detail["element_id"] = exc.element_id
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(DomainViolation)
async def handle_domain_violation(_request: Request, exc: DomainViolation):
    detail = {"code": exc.code, "message": exc.message}
    if exc.path:
        detail["path"] = exc.path
    if exc.element_id:
        detail["element_id"] = exc.element_id
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(IntegrityError)
async def handle_integrity_error(_request: Request, _exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": {
                "code": "data_conflict",
                "message": "数据已发生变化或违反关联约束，请刷新后重试",
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(_request: Request, exc: RequestValidationError):
    error = exc.errors()[0] if exc.errors() else {}
    location = error.get("loc", ())
    path = ".".join(str(part) for part in location if part != "body") or None
    detail = {
        "code": "request_validation_failed",
        "message": _request_validation_message(error),
    }
    if path:
        detail["path"] = path
    element_id = await _request_element_id(_request, location)
    if element_id:
        detail["element_id"] = element_id
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(ResponseValidationError)
async def handle_response_validation_error(_request: Request, exc: ResponseValidationError):
    error_id = uuid4().hex[:12]
    logger.error(
        "Invalid response payload [%s] %s %s",
        error_id,
        _request.method,
        _request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    error = exc.errors()[0] if exc.errors() else {}
    location = error.get("loc", ())
    path = ".".join(str(part) for part in location if part != "response") or None
    detail = {
        "code": "response_validation_failed",
        "message": f"服务端返回数据结构不符合接口定义，请提供错误编号：{error_id}",
    }
    if path:
        detail["path"] = path
    return JSONResponse(status_code=500, content={"detail": detail})


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    error_id = uuid4().hex[:12]
    logger.error(
        "Unhandled request error [%s] %s %s",
        error_id,
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "internal_server_error",
                "message": f"服务端处理失败，请联系管理员并提供错误编号：{error_id}",
            }
        },
    )


def _request_validation_message(error: dict) -> str:
    error_type = error.get("type")
    context = error.get("ctx") or {}
    if error_type == "missing":
        return "缺少必填内容"
    if error_type in {"string_too_short", "too_short"}:
        return "内容不能为空"
    if error_type in {"greater_than", "greater_than_equal"}:
        limit = context.get("gt", context.get("ge"))
        return f"数值必须大于{limit}" if error_type == "greater_than" else f"数值不能小于{limit}"
    if error_type in {"string_too_long", "too_long"}:
        return "内容超过允许长度"
    if error_type == "literal_error":
        return "流程版本或节点类型不正确"
    if error_type == "extra_forbidden":
        return "请求包含不支持的字段"
    return "请求数据格式错误"


async def _request_element_id(request: Request, location: tuple) -> str | None:
    try:
        body = await request.json()
    except Exception:
        return None
    for collection in ("nodes", "edges"):
        if collection not in location:
            continue
        position = location.index(collection)
        if position + 1 >= len(location) or not isinstance(location[position + 1], int):
            continue
        index = location[position + 1]
        flow = body.get("process_flow", body) if isinstance(body, dict) else {}
        items = flow.get(collection, []) if isinstance(flow, dict) else []
        if 0 <= index < len(items) and isinstance(items[index], dict):
            element_id = items[index].get("id")
            return element_id if isinstance(element_id, str) else None
    return None

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def validate_request_origin(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and not settings.allows_origin(origin):
            return JSONResponse(status_code=403, content={"detail": "请求来源不受信任"})

    return await call_next(request)


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(products.router)
app.include_router(organization.router)
app.include_router(customers.router)
app.include_router(customer_orders.router)
app.include_router(pmc.router)
app.include_router(production.router)
app.include_router(procedure_tag_prices.router)
app.include_router(work_orders.router)
app.include_router(qc.router)


@app.get("/")
def root():
    return {"message": "zzerp backend running"}


@app.head("/health")
def health_head():
    return
