from pathlib import Path
import os

from fastapi import HTTPException, UploadFile

from app.config import BACKEND_DIR


MODEL_DIR = Path(
    os.getenv("SKYGUARD_MODELS_DIR", str(BACKEND_DIR / "model_weights"))
).resolve()
MAX_MODEL_BYTES = 2 * 1024 * 1024 * 1024
MODEL_UPLOAD_ENABLED = os.getenv("SKYGUARD_ALLOW_MODEL_UPLOAD", "false").lower() == "true"


def list_models() -> list[dict[str, str | bool]]:
    models: dict[str, dict[str, str | bool]] = {}
    default_path = os.getenv("SKYGUARD_MODEL_PATH")
    if default_path:
        legacy_path = Path(default_path).expanduser().resolve()
        if legacy_path.is_file() and legacy_path.suffix.lower() == ".pt":
            models[f"env:{legacy_path.name}"] = {
                "id": f"env:{legacy_path.name}",
                "name": legacy_path.stem,
                "is_default": True,
            }

    if MODEL_DIR.is_dir():
        for model_path in MODEL_DIR.glob("*.pt"):
            if model_path.is_file():
                models[model_path.name] = {
                    "id": model_path.name,
                    "name": model_path.stem,
                    "is_default": False,
                }

    return sorted(models.values(), key=lambda item: str(item["name"]).casefold())


def resolve_model(model_id: str | None) -> tuple[Path, str]:
    default_path = os.getenv("SKYGUARD_MODEL_PATH")
    if model_id and model_id.startswith("env:"):
        env_name = model_id.removeprefix("env:")
        if default_path:
            path = Path(default_path).expanduser().resolve()
            if path.name == env_name and path.is_file():
                return path, path.stem
        raise HTTPException(status_code=404, detail="Configured default model not found")

    if not model_id:
        if not default_path:
            raise HTTPException(
                status_code=400,
                detail="Choose a model before starting detection",
            )
        path = Path(default_path).expanduser().resolve()
        if path.is_file():
            return path, path.stem
        raise HTTPException(status_code=404, detail="Configured default model not found")

    model_name = Path(model_id).name
    if model_name != model_id or not model_name.lower().endswith(".pt"):
        raise HTTPException(status_code=400, detail="Invalid model selection")

    candidate = (MODEL_DIR / model_name).resolve()
    try:
        candidate.relative_to(MODEL_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid model selection") from exc

    if candidate.is_file():
        return candidate, candidate.stem

    if default_path:
        legacy_path = Path(default_path).expanduser().resolve()
        if legacy_path.name == model_name and legacy_path.is_file():
            return legacy_path, legacy_path.stem

    raise HTTPException(status_code=404, detail="Selected model was not found")


async def save_uploaded_model(upload: UploadFile) -> dict[str, str | bool]:
    if not MODEL_UPLOAD_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Model uploads are disabled. Set SKYGUARD_ALLOW_MODEL_UPLOAD=true for trusted local development.",
        )

    original_name = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    model_name = Path(original_name).stem.strip()
    if (
        Path(original_name).name != original_name
        or Path(original_name).suffix.lower() != ".pt"
        or not model_name
        or model_name in {".", ".."}
        or len(model_name) > 120
    ):
        raise HTTPException(
            status_code=415,
            detail="Upload a .pt weight file named with the dataset name",
        )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    destination = MODEL_DIR / f"{model_name}.pt"
    if destination.exists():
        raise HTTPException(
            status_code=409,
            detail="A model with this dataset name already exists",
        )

    size = 0
    try:
        with destination.open("xb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_MODEL_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Model file exceeds the 2 GiB upload limit",
                    )
                output.write(chunk)
        if not size:
            raise HTTPException(status_code=400, detail="Model file is empty")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return {"id": destination.name, "name": model_name, "is_default": False}
