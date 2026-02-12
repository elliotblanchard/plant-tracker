"""Plant segmentation using PlantCV and OpenCV.

Segments the green Marchantia tissue from the background and returns the
binary mask plus the plant area in pixels.
"""

import logging
from dataclasses import dataclass

import cv2
import numpy as np
from plantcv import plantcv as pcv

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SegmentationResult:
    """Output of the plant segmentation step."""

    mask: np.ndarray        # Binary mask (0/255), same H×W as input
    area_px: int            # Number of plant pixels
    contour: np.ndarray | None  # Largest contour (for visualization)
    success: bool


def segment_plant(image: np.ndarray) -> SegmentationResult:
    """Segment the Marchantia plant from the background.

    Uses HSV color-space thresholding followed by morphological cleanup.
    Falls back to PlantCV's naive-Bayes-style approach if the simple
    threshold yields nothing.

    Args:
        image: BGR image (NumPy array).

    Returns:
        ``SegmentationResult`` with mask and area in pixels.
    """
    # Suppress PlantCV's verbose debug output
    pcv.params.debug = None

    # --- HSV-based green thresholding -----------------------------------
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    lower = np.array([settings.hue_lower, settings.saturation_lower, settings.value_lower])
    upper = np.array([settings.hue_upper, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    # --- Morphological cleanup ------------------------------------------
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Remove small blobs
    mask = _remove_small_components(mask, settings.min_plant_area_px)

    area_px = int(cv2.countNonZero(mask))

    if area_px < settings.min_plant_area_px:
        # Fallback: use PlantCV's white-balance + threshold pipeline
        logger.info("HSV mask too small (%d px), trying PlantCV fallback", area_px)
        mask, area_px = _plantcv_fallback(image)

    if area_px < settings.min_plant_area_px:
        logger.warning("Segmentation failed: plant area %d px below minimum", area_px)
        return SegmentationResult(mask=mask, area_px=area_px, contour=None, success=False)

    # Find largest contour for downstream use
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = max(contours, key=cv2.contourArea) if contours else None

    logger.info("Segmented plant: %d pixels", area_px)
    return SegmentationResult(mask=mask, area_px=area_px, contour=largest, success=True)


def _remove_small_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    """Remove connected components smaller than *min_area* pixels."""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    cleaned = np.zeros_like(mask)
    for i in range(1, num_labels):  # skip background label 0
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            cleaned[labels == i] = 255
    return cleaned


def _plantcv_fallback(image: np.ndarray) -> tuple[np.ndarray, int]:
    """Attempt segmentation using PlantCV color-space channels.

    This is a simpler fallback that uses the a-channel (green-magenta)
    from the LAB color space, which often separates green plant tissue
    well from non-green backgrounds.
    """
    # Convert to LAB and threshold the a-channel (green vs magenta)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    _, a_channel, _ = cv2.split(lab)

    # Green tissue has LOW a-values in LAB; threshold below midpoint
    _, mask = cv2.threshold(a_channel, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = _remove_small_components(mask, settings.min_plant_area_px)

    area_px = int(cv2.countNonZero(mask))
    return mask, area_px
