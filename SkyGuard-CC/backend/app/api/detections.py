from pathlib import Path
from uuid import uuid4

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import BACKEND_DIR
from app.database import SessionLocal
from app.models import DetectionTask, ImageRecord
from app.schemas import DetectionTaskRead
from app.services.detection_service import create_detection
from app.services.model_registry import resolve_model


router = APIRouter(prefix="/api/detections", tags=["detections"])

UPLOAD_DIR = BACKEND_DIR.parent / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
FORMAT_EXTENSIONS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "WEBP": {".webp"},
    "TIFF": {".tif", ".tiff"},
}
FORMAT_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "TIFF": "image/tiff",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _save_and_validate_image(
    upload: UploadFile,
) -> tuple[Path, str, int, int, int, str]:
    original_filename = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not original_filename or len(original_filename) > 255:
        raise HTTPException(status_code=400, detail="Invalid image filename")

    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Only JPG, PNG, WEBP, and TIFF images are supported",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_file = UPLOAD_DIR / f"{uuid4().hex}{extension}"
    file_size = 0

    try:
        with stored_file.open("xb") as destination:
            while chunk := upload.file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Image exceeds the 10 MiB upload limit",
                    )
                destination.write(chunk)

        with Image.open(stored_file) as image:
            image_format = image.format
            image.verify()
        if (
            image_format not in FORMAT_EXTENSIONS
            or extension not in FORMAT_EXTENSIONS[image_format]
        ):
            raise HTTPException(
                status_code=415,
                detail="File extension does not match a supported image format",
            )

        with Image.open(stored_file) as image:
            width, height = image.size
        if width <= 0 or height <= 0 or width * height > 100_000_000:
            raise HTTPException(status_code=400, detail="Image dimensions are invalid")

        return (
            stored_file,
            original_filename,
            file_size,
            width,
            height,
            FORMAT_MIME_TYPES[image_format],
        )
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        stored_file.unlink(missing_ok=True)
        raise HTTPException(
            status_code=415, detail="Uploaded file is not a valid image"
        ) from exc
    except Exception:
        stored_file.unlink(missing_ok=True)
        raise


@router.post(
    "",
    response_model=DetectionTaskRead,
    status_code=201,
    summary="Upload an image and run OBB detection",
)
def upload_and_detect(
    file: UploadFile = File(...),
    confidence: float = Form(default=0.25, ge=0.0, le=1.0),
    nms_iou: float = Form(default=0.45, ge=0.0, le=1.0),
    model_id: str | None = Form(default=None, max_length=255),
    db: Session = Depends(get_db),
):
    selected_model_path, selected_model_name = resolve_model(model_id)
    (
        stored_file,
        original_filename,
        file_size,
        width,
        height,
        mime_type,
    ) = _save_and_validate_image(file)
    try:
        return create_detection(
            db,
            image_path=str(stored_file),
            original_filename=original_filename,
            stored_path=stored_file.relative_to(BACKEND_DIR.parent).as_posix(),
            mime_type=mime_type,
            file_size=file_size,
            image_width=width,
            image_height=height,
            confidence=confidence,
            nms_iou=nms_iou,
            model_path=str(selected_model_path),
            model_name=selected_model_name,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        stored_file.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail="Model inference is unavailable. Check the model path, Ultralytics installation, and OBB weights.",
        ) from exc
    except Exception as exc:
        stored_file.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not save detection record") from exc
    finally:
        file.file.close()


@router.get("", response_model=list[DetectionTaskRead], summary="List detection history")
def list_detections(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    statement = (
        select(DetectionTask)
        .options(
            selectinload(DetectionTask.results),
            selectinload(DetectionTask.image),
        )
        .order_by(DetectionTask.created_at.desc(), DetectionTask.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(statement).all()


@router.get("/query", summary="Search detection history with pagination")
def query_detections(
    q: str = Query(default="", max_length=255),
    status: str | None = Query(default=None, pattern="^(pending|running|succeeded|failed)$"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be on or before date_to",
        )

    filters = []
    if q.strip():
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                ImageRecord.original_filename.ilike(term),
                cast(DetectionTask.id, String).ilike(term),
            )
        )
    if status:
        filters.append(DetectionTask.status == status)
    if date_from:
        filters.append(
            DetectionTask.created_at >= datetime.combine(date_from, time.min)
        )
    if date_to:
        filters.append(
            DetectionTask.created_at
            < datetime.combine(date_to + timedelta(days=1), time.min)
        )

    base = select(DetectionTask).join(ImageRecord)
    if filters:
        base = base.where(*filters)
    total = db.scalar(
        select(func.count(func.distinct(DetectionTask.id)))
        .select_from(DetectionTask)
        .join(ImageRecord)
        .where(*filters)
    ) if filters else db.scalar(select(func.count(DetectionTask.id)))
    statement = (
        base.options(
            selectinload(DetectionTask.results),
            selectinload(DetectionTask.image),
        )
        .order_by(DetectionTask.created_at.desc(), DetectionTask.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": db.scalars(statement).all(),
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/images/{image_id}/content", summary="Read an uploaded image")
def get_image_content(image_id: int, db: Session = Depends(get_db)):
    image = db.get(ImageRecord, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    upload_root = UPLOAD_DIR.resolve()
    image_path = (BACKEND_DIR.parent / image.stored_path).resolve()
    try:
        image_path.relative_to(upload_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Image not found") from exc
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(image_path, media_type=image.mime_type)


@router.get("/{task_id}/annotated/status", summary="Check for a detection visualization")
def get_annotated_image_status(task_id: int, db: Session = Depends(get_db)):
    if db.get(DetectionTask, task_id) is None:
        raise HTTPException(status_code=404, detail="Detection task not found")
    image_path = UPLOAD_DIR / "predictions" / f"task-{task_id}.jpg"
    return {"available": image_path.is_file()}


@router.get("/{task_id}/annotated", summary="Read the detection visualization")
def get_annotated_image(task_id: int, db: Session = Depends(get_db)):
    if db.get(DetectionTask, task_id) is None:
        raise HTTPException(status_code=404, detail="Detection task not found")
    output_root = (UPLOAD_DIR / "predictions").resolve()
    image_path = (output_root / f"task-{task_id}.jpg").resolve()
    try:
        image_path.relative_to(output_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Image not found") from exc
    if not image_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="No prediction image is available for this task",
        )
    return FileResponse(image_path, media_type="image/jpeg")


@router.get("/{task_id}", response_model=DetectionTaskRead, summary="Get detection details")
def get_detection(task_id: int, db: Session = Depends(get_db)):
    statement = (
        select(DetectionTask)
        .options(
            selectinload(DetectionTask.results),
            selectinload(DetectionTask.image),
        )
        .where(DetectionTask.id == task_id)
    )
    task = db.scalar(statement)
    if task is None:
        raise HTTPException(status_code=404, detail="Detection task not found")
    return task
