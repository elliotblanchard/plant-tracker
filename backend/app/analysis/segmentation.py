"""Plant segmentation using PlantCV and OpenCV.

Segments the green Marchantia tissue from the background and returns the
binary mask plus the plant area in pixels.

Before HSV thresholding, the image is masked to the petri dish region
(via Hough circle detection) to exclude the color chart, QR code, ruler,
and other non-plant features.
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
    dish_circle: tuple[int, int, int] | None = None  # (cx, cy, r) if detected


def segment_plant(image: np.ndarray) -> SegmentationResult:
    """Segment the Marchantia plant from the background.

    Pipeline:
    1. Detect the petri dish (Hough circles) and create a circular ROI mask.
    2. Apply HSV green thresholding within the ROI.
    3. Morphological cleanup and small-blob removal.
    4. Fallback to LAB a-channel if HSV yields nothing.

    Args:
        image: BGR image (NumPy array).

    Returns:
        ``SegmentationResult`` with mask and area in pixels.
    """
    pcv.params.debug = None
    h, w = image.shape[:2]

    # --- Step 0: Build an ROI mask (petri dish or exclusion zones) ------
    roi_mask, dish_circle = _build_roi_mask(image)

    # --- Step 1: HSV-based green thresholding ---------------------------
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    lower = np.array([settings.hue_lower, settings.saturation_lower, settings.value_lower])
    upper = np.array([settings.hue_upper, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    # Apply the ROI mask to restrict to dish area
    if roi_mask is not None:
        mask = cv2.bitwise_and(mask, roi_mask)

    # --- Step 2: Morphological cleanup ----------------------------------
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    mask = _remove_small_components(mask, settings.min_plant_area_px)
    area_px = int(cv2.countNonZero(mask))

    if area_px < settings.min_plant_area_px:
        logger.info("HSV mask too small (%d px), trying PlantCV fallback", area_px)
        mask, area_px = _plantcv_fallback(image, roi_mask)

    if area_px < settings.min_plant_area_px:
        logger.warning("Segmentation failed: plant area %d px below minimum", area_px)
        return SegmentationResult(
            mask=mask, area_px=area_px, contour=None, success=False,
            dish_circle=dish_circle,
        )

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = max(contours, key=cv2.contourArea) if contours else None

    logger.info("Segmented plant: %d pixels", area_px)
    return SegmentationResult(
        mask=mask, area_px=area_px, contour=largest, success=True,
        dish_circle=dish_circle,
    )


# ── ROI / Dish Detection ─────────────────────────────────────────────


def _build_roi_mask(image: np.ndarray) -> tuple[np.ndarray | None, tuple[int, int, int] | None]:
    """Create a mask that restricts processing to the plant region.

    Uses configured exclusion zones to mask out the color chart, QR code,
    and ruler strip.  These are reliable for a standardized camera setup.

    Returns:
        (roi_mask, dish_circle) where roi_mask is a uint8 mask (0/255) and
        dish_circle is always None (reserved for future circle detection).
    """
    h, w = image.shape[:2]

    exclusion_zones = settings.exclusion_zones
    if exclusion_zones:
        roi_mask = np.full((h, w), 255, dtype=np.uint8)
        for zone in exclusion_zones:
            x, y, zw, zh = zone
            roi_mask[y : y + zh, x : x + zw] = 0
        logger.info("Applied %d exclusion zones", len(exclusion_zones))
        return roi_mask, None

    logger.warning("No exclusion zones configured -- segmenting full image")
    return None, None


def _detect_petri_dish(image: np.ndarray) -> tuple[int, int, int] | None:
    """Detect the circular petri dish using Hough circle detection.

    Returns (cx, cy, radius) of the best circle, or None.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    h, w = gray.shape
    min_radius = min(h, w) // 5
    max_radius = min(h, w) // 2

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min(h, w) // 3,
        param1=100,
        param2=40,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    if circles is None:
        return None

    # Pick the largest circle (most likely to be the petri dish)
    circles = np.round(circles[0]).astype(int)
    best = max(circles, key=lambda c: c[2])
    return int(best[0]), int(best[1]), int(best[2])


# ── Cleanup Helpers ───────────────────────────────────────────────────


def _remove_small_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    """Remove connected components smaller than *min_area* pixels."""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    cleaned = np.zeros_like(mask)
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            cleaned[labels == i] = 255
    return cleaned


def _plantcv_fallback(
    image: np.ndarray, roi_mask: np.ndarray | None
) -> tuple[np.ndarray, int]:
    """Fallback segmentation using the LAB a-channel."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    _, a_channel, _ = cv2.split(lab)

    _, mask = cv2.threshold(a_channel, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    if roi_mask is not None:
        mask = cv2.bitwise_and(mask, roi_mask)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = _remove_small_components(mask, settings.min_plant_area_px)

    area_px = int(cv2.countNonZero(mask))
    return mask, area_px
