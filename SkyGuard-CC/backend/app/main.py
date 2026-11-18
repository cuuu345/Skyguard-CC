from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.detections import router as detections_router
from app.api.analytics import router as analytics_router
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.database import Base, engine
import app.models  # Register ORM tables before create_all.


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="SkyGuard API", lifespan=lifespan)
app.include_router(health_router)
app.include_router(detections_router)
app.include_router(analytics_router)
app.include_router(models_router)


@app.get("/")
def home():
    return {"message": "SkyGuard 后端已启动"}


