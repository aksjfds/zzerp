import logging

from fastapi import Depends
from fastapi.responses import JSONResponse

from zzerp.database import Database
from zzerp.http.dependencies import get_database

logger = logging.getLogger(__name__)


def root():
    return {"message": "zzerp backend running"}


def health():
    return {"status": "ok"}


def readiness(database: Database = Depends(get_database)):
    try:
        ready = database.is_ready()
    except Exception:
        logger.exception("Database readiness check failed")
        return JSONResponse(
            status_code=503, content={"status": "unavailable", "database": "unreachable"}
        )
    if not ready:
        return JSONResponse(
            status_code=503, content={"status": "unavailable", "database": "schema_missing"}
        )
    return {"status": "ready", "database": "ready"}
