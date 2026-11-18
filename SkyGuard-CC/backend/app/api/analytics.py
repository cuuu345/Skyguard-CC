from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.detections import get_db
from app.models import DetectionResult, DetectionTask, ImageRecord


router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    today = date.today()
    week_start = today - timedelta(days=6)
    week_start_at = datetime.combine(week_start, time.min)

    image_count = db.scalar(select(func.count(ImageRecord.id))) or 0
    task_count = db.scalar(select(func.count(DetectionTask.id))) or 0
    result_count = db.scalar(select(func.count(DetectionResult.id))) or 0
    average_confidence = db.scalar(select(func.avg(DetectionResult.confidence)))

    category_rows = db.execute(
        select(
            DetectionResult.class_id,
            DetectionResult.class_name,
            func.count(DetectionResult.id),
        )
        .group_by(DetectionResult.class_id, DetectionResult.class_name)
        .order_by(func.count(DetectionResult.id).desc())
    ).all()

    daily_rows = db.execute(
        select(
            func.date(DetectionTask.created_at),
            func.count(DetectionTask.id),
        )
        .where(DetectionTask.created_at >= week_start_at)
        .group_by(func.date(DetectionTask.created_at))
    ).all()
    daily_counts = {str(day): count for day, count in daily_rows}
    daily_tasks = [
        {
            "date": (week_start + timedelta(days=offset)).isoformat(),
            "count": daily_counts.get(
                (week_start + timedelta(days=offset)).isoformat(), 0
            ),
        }
        for offset in range(7)
    ]

    return {
        "image_count": image_count,
        "task_count": task_count,
        "result_count": result_count,
        "average_confidence": (
            round(float(average_confidence), 6)
            if average_confidence is not None
            else None
        ),
        "accuracy": None,
        "categories": [
            {"class_id": class_id, "class_name": name, "count": count}
            for class_id, name, count in category_rows
        ],
        "daily_tasks": daily_tasks,
    }
