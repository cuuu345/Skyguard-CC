from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Point2D = tuple[float, float]
RotatedBoxPoints = tuple[Point2D, Point2D, Point2D, Point2D]
TaskStatus = Literal["pending", "running", "succeeded", "failed"]


class SchemaBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class ORMReadSchema(SchemaBase):
    model_config = ConfigDict(from_attributes=True)


class ImageRecordCreate(SchemaBase):
    original_filename: str = Field(min_length=1, max_length=255)
    stored_path: str = Field(min_length=1, max_length=1024)
    mime_type: str | None = Field(default=None, max_length=100)
    file_size: int = Field(ge=0)
    image_width: int | None = Field(default=None, gt=0)
    image_height: int | None = Field(default=None, gt=0)


class ImageRecordRead(ORMReadSchema):
    id: int
    original_filename: str
    stored_path: str
    mime_type: str | None
    file_size: int
    image_width: int | None
    image_height: int | None
    created_at: datetime


class ImageSummaryRead(ORMReadSchema):
    id: int
    original_filename: str
    mime_type: str | None
    file_size: int
    image_width: int | None
    image_height: int | None
    created_at: datetime


class DetectionTaskCreate(SchemaBase):
    image_id: int = Field(gt=0)
    model_name: str | None = Field(default=None, max_length=255)


class DetectionResultCreate(SchemaBase):
    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1, max_length=255)
    confidence: float = Field(ge=0, le=1)
    points: RotatedBoxPoints


class DetectionResultRead(ORMReadSchema):
    id: int
    task_id: int
    class_id: int
    class_name: str
    confidence: float
    points: RotatedBoxPoints
    created_at: datetime


class DetectionTaskRead(ORMReadSchema):
    id: int
    image_id: int
    image: ImageSummaryRead
    status: TaskStatus
    model_name: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    results: list[DetectionResultRead] = Field(default_factory=list)
