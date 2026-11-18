from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from PIL import Image

from app.model_adapter import detect_image
from app.config import BACKEND_DIR
from app.models import DetectionResult, DetectionTask, ImageRecord


def create_detection(
    db: Session,
    *,
    image_path: str,
    original_filename: str,
    stored_path: str,
    mime_type: str,
    file_size: int,
    image_width: int,
    image_height: int,
    confidence: float | None = None,
    nms_iou: float | None = None,
    model_path: str | None = None,
    model_name: str | None = None,
) -> DetectionTask:
    """Run OBB inference and persist its real detections."""
    prediction = detect_image(
        image_path,
        confidence=confidence,
        nms_iou=nms_iou,
        model_path=model_path,
    )
    predicted_width = int(prediction["image_width"])
    predicted_height = int(prediction["image_height"])
    if predicted_width != image_width or predicted_height != image_height:
        raise RuntimeError(
            "Image dimensions changed between upload validation and model inference."
        )

    detected_model_name = str(
        prediction.get(
            "model_name",
            "unknown-obb-model",
        )
    )
    now = datetime.now(timezone.utc)
    image = ImageRecord(
        original_filename=original_filename,
        stored_path=stored_path,
        mime_type=mime_type,
        file_size=file_size,
        image_width=predicted_width,
        image_height=predicted_height,
    )
    task = DetectionTask(
        image=image,
        status="succeeded",
        model_name=model_name or detected_model_name,
        started_at=now,
        completed_at=now,
    )
    task.results.extend(
        DetectionResult(
            class_id=int(detection["class_id"]),
            class_name=str(detection["class_name"]),
            confidence=float(detection["confidence"]),
            points=[
                [float(point[0]), float(point[1])]
                for point in detection["points"]
            ],
        )
        for detection in prediction["detections"]
    )

    try:
        db.add(task)
        db.flush()
        annotated = prediction["annotated_image"]
        if annotated is None or annotated.ndim != 3:
            raise RuntimeError("The model did not produce an annotated image.")
        output_dir = BACKEND_DIR.parent / "uploads" / "predictions"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"task-{task.id}.jpg"
        Image.fromarray(annotated[:, :, ::-1].copy()).save(
            output_path,
            format="JPEG",
            quality=92,
        )
        db.commit()
        db.refresh(task)
        return db.scalar(
            select(DetectionTask)
            .options(
                selectinload(DetectionTask.results),
                selectinload(DetectionTask.image),
            )
            .where(DetectionTask.id == task.id)
        )
    except Exception:
        db.rollback()
        if "output_path" in locals():
            output_path.unlink(missing_ok=True)
        raise
