"""SkyGuard YOLO OBB adapter.

This module keeps model-specific code in one place.  The rest of the
application can call ``detect_image()`` without knowing Ultralytics details.
"""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Any


_model: Any | None = None
_loaded_model_path: str | None = None
_model_lock = Lock()


def _load_model(model_path: str | None = None) -> Any:
    """Keep only the currently selected checkpoint in memory."""
    global _model, _loaded_model_path

    configured_path = model_path or os.getenv("SKYGUARD_MODEL_PATH")
    if not configured_path:
        raise RuntimeError(
            "No model was selected and SKYGUARD_MODEL_PATH is not set."
        )

    model_file = Path(configured_path).resolve()
    if not model_file.is_file():
        raise FileNotFoundError(f"Model file does not exist: {model_file}")
    cache_key = str(model_file)
    if _model is not None and _loaded_model_path == cache_key:
        return _model

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "The ultralytics package is required. "
            "Install it with: pip install ultralytics"
        ) from exc

    model = YOLO(str(model_file))
    _model = model
    _loaded_model_path = cache_key
    return model


def _to_python(value: Any) -> Any:
    """Convert tensors and NumPy values into JSON-serializable Python values."""
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return value


def _get_image_size(image_path: Path, result: Any) -> tuple[int, int]:
    """Read image dimensions, preferring the dimensions reported by inference."""
    original_shape = getattr(result, "orig_shape", None)
    if original_shape is not None and len(original_shape) >= 2:
        height, width = original_shape[:2]
        return int(width), int(height)

    try:
        from PIL import Image

        with Image.open(image_path) as image:
            return image.width, image.height
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required when the model result does not include image size. "
            "Install it with: pip install pillow"
        ) from exc


def _get_model_name(model: Any, model_path: str | None) -> str:
    return Path(model_path or os.getenv("SKYGUARD_MODEL_PATH", "model")).stem


def _parse_obb_result(result: Any) -> list[dict[str, Any]]:
    """Convert one Ultralytics OBB result into the platform result format."""
    obb = getattr(result, "obb", None)
    if obb is None:
        raise RuntimeError(
            "The model result does not contain OBB data. "
            "Check that the loaded model is an oriented-bounding-box model."
        )

    points_data = getattr(obb, "xyxyxyxy", None)
    class_data = getattr(obb, "cls", None)
    confidence_data = getattr(obb, "conf", None)
    if points_data is None or class_data is None or confidence_data is None:
        raise RuntimeError(
            "The OBB result is missing xyxyxyxy, cls, or conf fields."
        )

    points = _to_python(points_data)
    classes = _to_python(class_data)
    confidences = _to_python(confidence_data)
    names = getattr(result, "names", {}) or {}

    detections: list[dict[str, Any]] = []
    for item_points, item_class, item_confidence in zip(
        points, classes, confidences
    ):
        class_id = int(item_class)
        if isinstance(names, dict):
            class_name = str(names.get(class_id, class_id))
        else:
            class_name = str(names[class_id])

        detections.append(
            {
                "class_id": class_id,
                "class_name": class_name,
                "confidence": round(float(item_confidence), 6),
                "points": [
                    [round(float(point[0]), 3), round(float(point[1]), 3)]
                    for point in item_points
                ],
            }
        )

    return detections


def detect_image(
    image_path: str,
    *,
    confidence: float | None = None,
    nms_iou: float | None = None,
    model_path: str | None = None,
) -> dict[str, Any]:
    """Run OBB detection and return a stable JSON-friendly result.

    Args:
        image_path: Local path to the image that should be analyzed.

    Returns:
        A dictionary containing the original image size and detected objects.

    Raises:
        FileNotFoundError: If ``image_path`` does not exist.
        RuntimeError: If the model or its OBB output cannot be used.
    """
    image_file = Path(image_path)
    if not image_file.is_file():
        raise FileNotFoundError(f"Image file does not exist: {image_file}")

    predict_options: dict[str, Any] = {
        "source": str(image_file),
        "conf": confidence
        if confidence is not None
        else float(os.getenv("SKYGUARD_CONFIDENCE", "0.25")),
        "iou": nms_iou
        if nms_iou is not None
        else float(os.getenv("SKYGUARD_NMS_IOU", "0.45")),
        "verbose": False,
    }

    device = os.getenv("SKYGUARD_DEVICE")
    if device:
        predict_options["device"] = device

    image_size = os.getenv("SKYGUARD_IMAGE_SIZE")
    if image_size:
        predict_options["imgsz"] = int(image_size)

    with _model_lock:
        model = _load_model(model_path)
        results = model.predict(**predict_options)
    if not results:
        raise RuntimeError("The model returned no result.")

    result = results[0]
    width, height = _get_image_size(image_file, result)
    return {
        "model_name": _get_model_name(model, model_path),
        "image_width": width,
        "image_height": height,
        "detections": _parse_obb_result(result),
        "annotated_image": result.plot(),
    }
