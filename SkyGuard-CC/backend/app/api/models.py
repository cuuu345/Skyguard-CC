from fastapi import APIRouter, File, UploadFile

from app.services.model_registry import (
    MODEL_UPLOAD_ENABLED,
    list_models,
    save_uploaded_model,
)


router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def get_models():
    return {
        "items": list_models(),
        "upload_enabled": MODEL_UPLOAD_ENABLED,
    }


@router.post("", status_code=201)
async def upload_model(file: UploadFile = File(...)):
    """Store a trusted local Ultralytics OBB checkpoint under its dataset name."""
    return await save_uploaded_model(file)
