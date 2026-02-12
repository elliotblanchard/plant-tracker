"""Extract color metrics from the segmented plant region.

Computes mean hue, mean saturation, and a greenness index for the
masked plant pixels only.
"""

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ColorMetrics:
    """Color-derived features of the plant tissue."""

    mean_hue: float          # Mean hue (0–180, OpenCV convention)
    mean_saturation: float   # Mean saturation (0–255 → normalized 0–1)
    greenness_index: float   # (2*G - R - B) / (R + G + B), range roughly -1..+1


def extract_color_metrics(image: np.ndarray, mask: np.ndarray) -> ColorMetrics:
    """Compute color features over the plant-masked region.

    Args:
        image: BGR image (NumPy array).
        mask: Binary mask (0/255) of the plant region.

    Returns:
        ``ColorMetrics`` with hue, saturation, and greenness values.
    """
    # HSV statistics
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    plant_pixels_hsv = hsv[mask > 0]

    if len(plant_pixels_hsv) == 0:
        logger.warning("No plant pixels for color analysis; returning zeros")
        return ColorMetrics(mean_hue=0.0, mean_saturation=0.0, greenness_index=0.0)

    mean_hue = float(np.mean(plant_pixels_hsv[:, 0]))
    mean_saturation = float(np.mean(plant_pixels_hsv[:, 1]) / 255.0)

    # Greenness index from BGR channels
    plant_pixels_bgr = image[mask > 0].astype(np.float64)
    b_mean = np.mean(plant_pixels_bgr[:, 0])
    g_mean = np.mean(plant_pixels_bgr[:, 1])
    r_mean = np.mean(plant_pixels_bgr[:, 2])

    channel_sum = r_mean + g_mean + b_mean
    if channel_sum > 0:
        greenness_index = float((2.0 * g_mean - r_mean - b_mean) / channel_sum)
    else:
        greenness_index = 0.0

    logger.info(
        "Color metrics: hue=%.1f, sat=%.3f, greenness=%.3f",
        mean_hue,
        mean_saturation,
        greenness_index,
    )
    return ColorMetrics(
        mean_hue=mean_hue,
        mean_saturation=mean_saturation,
        greenness_index=greenness_index,
    )
