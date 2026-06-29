from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from routers import auth, products, qc, records, work_orders

app = FastAPI(title="zzerp")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
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
app.include_router(records.router)
app.include_router(work_orders.router)
app.include_router(qc.router)


@app.get("/")
def root():
    return {"message": "zzerp backend running"}


@app.head("/health")
def health_head():
    return
