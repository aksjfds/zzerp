import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from zzerp.errors import DomainError

logger = logging.getLogger(__name__)


async def handle_domain_error(_request: Request, exc: DomainError):
    detail = {"code": exc.code, "message": exc.message}
    if exc.path:
        detail["path"] = exc.path
    if exc.element_id:
        detail["element_id"] = exc.element_id
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


async def handle_integrity_error(request: Request, exc: IntegrityError):
    error_id = uuid4().hex[:12]
    logger.error(
        "Database integrity error [%s] %s %s",
        error_id,
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=409,
        content={
            "detail": {
                "code": "data_conflict",
                "message": (
                    "数据已发生变化或违反关联约束，请刷新后重试；"
                    f"如果问题持续，请提供错误编号：{error_id}"
                ),
            }
        },
    )


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


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(IntegrityError, handle_integrity_error)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(ResponseValidationError, handle_response_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
