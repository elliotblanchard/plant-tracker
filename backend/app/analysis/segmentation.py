"""Plant segmentation using PlantCV and OpenCV.

Segments the green Marchantia tissue from the background and returns the
binary mask plus the plant area in pixels.

Supports both single-plant (backward compatible) and multi-plant
segmentation using QR code positions to locate individual petri dishes.
"""

import logging
from dataclasses import dataclass

import cv2
import numpy as np
from plantcv import plantcv as pcv

from app.analysis.aruco_detection import ArucoMarker
from app.analysis.qr_detection import QRResult
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


@dataclass
class PlantSegmentationResult(SegmentationResult):
    """Per-plant segmentation result with QR code and dish region."""

    qr_code: str = ""
    dish_region: tuple[int, int, int, int] | None = None  # (x, y, w, h)


def segment_plant(image: np.ndarray) -> SegmentationResult:
    """Segment the Marchantia plant from the background (single-plant).

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
    mask = _hsv_threshold(image, roi_mask)

    # --- Step 2: Morphological cleanup ----------------------------------
    mask = _morphological_cleanup(mask)
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


def segment_plants(
    image: np.ndarray,
    qr_results: list[QRResult],
    aruco_markers: list[ArucoMarker] | None = None,
) -> list[PlantSegmentationResult]:
    """Segment multiple plants, one per QR code.

    Uses each QR code position as a search anchor, detects the nearest
    circular petri dish, and runs the HSV + morphology pipeline within
    that dish region.

    Args:
        image: BGR image (NumPy array).
        qr_results: Detected QR codes with positions.
        aruco_markers: Pre-detected ArUCO markers (unused for now, reserved).

    Returns:
        List of ``PlantSegmentationResult``, one per detected plant.
    """
    pcv.params.debug = None
    h, w = image.shape[:2]
    results: list[PlantSegmentationResult] = []

    if not qr_results:
        logger.info("No QR codes — falling back to single-plant segmentation")
        single = segment_plant(image)
        results.append(PlantSegmentationResult(
            mask=single.mask,
            area_px=single.area_px,
            contour=single.contour,
            success=single.success,
            dish_circle=single.dish_circle,
            qr_code="unknown-plant",
        ))
        return results

    for qr in qr_results:
        logger.info("Segmenting plant for QR: %s at (%d, %d)", qr.data, *qr.center)

        # Search for petri dish near the QR code
        dish = _detect_petri_dish_near(image, qr.center, settings.dish_search_radius_px)

        if dish is not None:
            cx, cy, r = dish
            # Create a circular mask for this dish
            roi_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(roi_mask, (cx, cy), r, 255, -1)
            dish_region = (max(0, cx - r), max(0, cy - r), 2 * r, 2 * r)
            logger.info("Dish found for %s at (%d, %d) r=%d", qr.data, cx, cy, r)
        else:
            # Fallback: use a square region around the QR code
            radius = settings.dish_search_radius_px
            x1, y1 = max(0, qr.center[0] - radius), max(0, qr.center[1] - radius)
            x2, y2 = min(w, qr.center[0] + radius), min(h, qr.center[1] + radius)
            roi_mask = np.zeros((h, w), dtype=np.uint8)
            roi_mask[y1:y2, x1:x2] = 255
            dish_region = (x1, y1, x2 - x1, y2 - y1)
            logger.warning("No dish detected for %s — using square ROI", qr.data)

        # HSV threshold within ROI
        mask = _hsv_threshold(image, roi_mask)
        mask = _morphological_cleanup(mask)
        area_px = int(cv2.countNonZero(mask))

        if area_px < settings.min_plant_area_px:
            mask, area_px = _plantcv_fallback(image, roi_mask)

        success = area_px >= settings.min_plant_area_px
        contour = None
        if success:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contour = max(contours, key=cv2.contourArea) if contours else None

        results.append(PlantSegmentationResult(
            mask=mask,
            area_px=area_px,
            contour=contour,
            success=success,
            dish_circle=dish if dish else None,
            qr_code=qr.data,
            dish_region=dish_region,
        ))
        logger.info("Plant %s: %d px, success=%s", qr.data, area_px, success)

    return results


# ── Shared Pipeline Steps ────────────────────────────────────────────

def _hsv_threshold(image: np.ndarray, roi_mask: np.ndarray | None) -> np.ndarray:
    """Apply HSV green thresholding, optionally restricted by ROI mask."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower = np.array([settings.hue_lower, settings.saturation_lower, settings.value_lower])
    upper = np.array([settings.hue_upper, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    if roi_mask is not None:
        mask = cv2.bitwise_and(mask, roi_mask)
    return mask


def _morphological_cleanup(mask: np.ndarray) -> np.ndarray:
    """Apply morphological close/open and remove small blobs."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = _remove_small_components(mask, settings.min_plant_area_px)
    return mask


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
        max_zone_extent = max(
            max(x + zw, y + zh) for x, y, zw, zh in exclusion_zones
        )
        if min(h, w) >= max_zone_extent * 0.5:
            roi_mask = np.full((h, w), 255, dtype=np.uint8)
            for zone in exclusion_zones:
                x, y, zw, zh = zone
                roi_mask[max(0, y) : min(h, y + zh), max(0, x) : min(w, x + zw)] = 0
            logger.info("Applied %d exclusion zones", len(exclusion_zones))
            return roi_mask, None
        logger.info("Image too small for configured exclusion zones -- skipping")

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

    circles = np.round(circles[0]).astype(int)
    best = max(circles, key=lambda c: c[2])
    return int(best[0]), int(best[1]), int(best[2])


def _detect_petri_dish_near(
    image: np.ndarray,
    anchor: tuple[int, int],
    search_radius: int,
) -> tuple[int, int, int] | None:
    """Detect a petri dish near a given anchor point (QR code position).

    Searches in a region around the anchor using Hough circles with
    radius range tuned for 4056×3040 images.

    Returns (cx, cy, radius) or None.
    """
    h, w = image.shape[:2]
    ax, ay = anchor

    # Crop a search window
    x1 = max(0, ax - search_radius)
    y1 = max(0, ay - search_radius)
    x2 = min(w, ax + search_radius)
    y2 = min(h, ay + search_radius)

    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    crop_h, crop_w = gray.shape
    min_radius = min(crop_h, crop_w) // 6
    max_radius = min(crop_h, crop_w) // 2

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_radius,
        param1=100,
        param2=40,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    if circles is None:
        return None

    circles = np.round(circles[0]).astype(int)

    # Pick the circle closest to the anchor
    best = None
    best_dist = float("inf")
    for c in circles:
        # Convert back to full-image coords
        cx_full = int(c[0]) + x1
        cy_full = int(c[1]) + y1
        dist = np.sqrt((cx_full - ax) ** 2 + (cy_full - ay) ** 2)
        if dist < best_dist:
            best_dist = dist
            best = (cx_full, cy_full, int(c[2]))

    return best


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
