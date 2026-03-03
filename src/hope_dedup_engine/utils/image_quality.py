import cv2
import numpy as np

from constance import config

from hope_dedup_engine.apps.api.models import Encoding


def michelson_contrast(image: np.ndarray) -> float:
    """Compute Michelson contrast on the luminance (Y) channel."""
    y = cv2.cvtColor(image, cv2.COLOR_BGR2YUV)[:, :, 0].astype(np.float32)
    min_y = float(y.min())
    max_y = float(y.max())
    return 0.0 if (denom := max_y + min_y) == 0.0 else (max_y - min_y) / denom


def image_quality_result(image_bgr: np.ndarray) -> tuple[Encoding.StatusCode | None, float | None]:
    if not config.DEFAULT_MICHELSON_CONTRAST_ENABLED:
        return None, None

    try:
        score = round(float(michelson_contrast(image_bgr)), 4)
    except (ValueError, TypeError, cv2.error):
        return None, None

    th = float(config.DEFAULT_MICHELSON_CONTRAST_THRESHOLD)
    status = Encoding.StatusCode.IMAGE_QUALITY_TOO_LOW if score < th else None
    return status, score
