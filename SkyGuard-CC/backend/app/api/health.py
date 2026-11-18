#(健康检查接口)

from fastapi import APIRouter
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine

router = APIRouter()


@router.get("/api/health")
def health_check():
    return {"status": "ok"}


@router.get("/api/db/health")
def database_health_check():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="MySQL connection or test query failed",
        ) from exc

    return {"status": "ok", "database": "mysql", "query_result": result}
