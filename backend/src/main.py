from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import auth, products, records, tasks

settings = get_settings()

app = FastAPI(title="zzerp")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(records.router)
app.include_router(tasks.router)


@app.get("/")
def root():
    return {"message": "zzerp backend running"}
