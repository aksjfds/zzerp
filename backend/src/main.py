from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from domain.errors import DomainViolation
from routers import auth, customer_orders, organization, production, products
from services.errors import DomainError

app = FastAPI(title="zzerp")
settings = get_settings()


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


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(_request: Request, exc: RequestValidationError):
    error = exc.errors()[0] if exc.errors() else {}
    location = error.get("loc", ())
    path = ".".join(str(part) for part in location if part != "body") or None
    detail = {
        "code": "request_validation_failed",
        "message": error.get("msg", "请求数据格式错误"),
    }
    if path:
        detail["path"] = path
    return JSONResponse(status_code=422, content={"detail": detail})

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def validate_request_origin(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "请求来源不受信任"})

    return await call_next(request)


app.include_router(auth.router)
app.include_router(products.router)
app.include_router(organization.router)
app.include_router(customer_orders.router)
app.include_router(production.router)


@app.get("/")
def root():
    return {"message": "zzerp backend running"}


@app.head("/health")
def health_head():
    return
