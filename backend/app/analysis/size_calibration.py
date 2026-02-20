"""Ruler-based size calibration: detect a ruler in the image and compute px_per_mm.

Strategy:
1. If a fixed ROI is configured, crop to that region.
2. Convert to grayscale, threshold to isolate high-contrast ruler markings.
3. Detect line segments via the Hough transform to locate the ruler spine.
4. Project tick marks onto the ruler axis and measure their spacing.
5. Use the known physical tick distance to compute pixels-per-mm.
"""

import logging
from dataclasses import dataclass

import cv2
import numpy as np
from scipy.signal import find_peaks

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    """Result of the ruler calibration step."""

    px_per_mm: float | None
    ruler_detected: bool
    tick_count: int = 0
    median_tick_spacing_px: float = 0.0


def calibrate_from_ruler(
    image: np.ndarray,
    tick_distance_mm: float | None = None,
    roi: list[int] | None = None,
) -> CalibrationResult:
    """Detect a ruler in the image and compute the pixel-to-mm conversion factor.

    Args:
        image: BGR image (NumPy array).
        tick_distance_mm: Physical distance between major ruler tick marks in mm.
            Defaults to ``settings.ruler_tick_distance_mm``.
        roi: Optional ``[x, y, w, h]`` rectangle to crop the ruler region.
            Defaults to ``settings.ruler_roi``.

    Returns:
        A ``CalibrationResult`` with ``px_per_mm`` (or ``None`` on failure).
    """
    tick_distance_mm = tick_distance_mm or settings.ruler_tick_distance_mm
    if roi is None:
        roi = settings.ruler_roi

    # Crop to ROI if provided and non-empty
    if roi is not None and len(roi) == 4:
        x, y, w, h = roi
        cropped = image[y : y + h, x : x + w]
        if cropped.size > 0:
            image = cropped

    if image.size == 0:
        return CalibrationResult(px_per_mm=None, ruler_detected=False)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Try both orientations and pick the one with more consistent ticks.
    # This avoids misclassification when vertical tick marks on a horizontal
    # ruler dominate Hough line detection.
    result_h = _find_tick_spacing(np.mean(gray, axis=0), tick_distance_mm)
    result_v = _find_tick_spacing(np.mean(gray, axis=1), tick_distance_mm)

    if result_h.px_per_mm is not None and result_v.px_per_mm is not None:
        return result_h if result_h.tick_count >= result_v.tick_count else result_v
    if result_h.px_per_mm is not None:
        return result_h
    if result_v.px_per_mm is not None:
        return result_v

    return CalibrationResult(px_per_mm=None, ruler_detected=False)


def _detect_ruler_orientation(gray: np.ndarray) -> tuple[str, float]:
    """Use Hough line detection to determine if the ruler is horizontal or vertical.

    Returns:
        A tuple of (orientation, dominant_angle) where orientation is one of
        ``"horizontal"``, ``"vertical"``, or ``"unknown"``.
    """
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=50, maxLineGap=10)

    if lines is None or len(lines) == 0:
        return "unknown", 0.0

    # Compute angle of each detected segment
    angles: list[float] = []
    lengths: list[float] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180
        length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        angles.append(angle)
        lengths.append(length)

    # Weight by length to find the dominant angle
    angles_arr = np.array(angles)
    lengths_arr = np.array(lengths)

    horizontal_mask = (angles_arr < 20) | (angles_arr > 160)
    vertical_mask = (angles_arr > 70) & (angles_arr < 110)

    h_weight = lengths_arr[horizontal_mask].sum() if horizontal_mask.any() else 0
    v_weight = lengths_arr[vertical_mask].sum() if vertical_mask.any() else 0

    if h_weight > v_weight and h_weight > 0:
        dominant = np.average(angles_arr[horizontal_mask], weights=lengths_arr[horizontal_mask])
        return "horizontal", float(dominant)
    elif v_weight > 0:
        dominant = np.average(angles_arr[vertical_mask], weights=lengths_arr[vertical_mask])
        return "vertical", float(dominant)

    return "unknown", 0.0


def _find_tick_spacing(profile: np.ndarray, tick_distance_mm: float) -> CalibrationResult:
    """Find evenly-spaced tick marks in a 1-D intensity profile.

    Args:
        profile: 1-D array of mean intensity values along the ruler axis.
        tick_distance_mm: Known physical distance between ticks (mm).

    Returns:
        ``CalibrationResult`` with pixel-per-mm conversion if enough ticks found.
    """
    # Smooth the profile to reduce noise
    kernel_size = max(3, len(profile) // 100)
    if kernel_size % 2 == 0:
        kernel_size += 1
    smoothed = cv2.GaussianBlur(profile.astype(np.float32), (kernel_size, 1), 0).flatten()

    # Invert so dark tick marks become peaks
    inverted = smoothed.max() - smoothed

    # Find peaks with minimum distance between tick marks
    min_distance = max(5, len(profile) // 150)
    prominence = (inverted.max() - inverted.min()) * 0.15
    peaks, properties = find_peaks(inverted, distance=min_distance, prominence=prominence)

    if len(peaks) < 3:
        logger.warning("Too few tick marks detected (%d) for reliable calibration", len(peaks))
        return CalibrationResult(px_per_mm=None, ruler_detected=False, tick_count=len(peaks))

    # Compute spacings between consecutive peaks
    spacings = np.diff(peaks).astype(float)

    # Filter out outlier spacings (keep those within 40% of the median)
    median_spacing = float(np.median(spacings))
    inlier_mask = np.abs(spacings - median_spacing) < 0.4 * median_spacing
    if inlier_mask.sum() < 2:
        logger.warning("Tick spacings too inconsistent for calibration")
        return CalibrationResult(
            px_per_mm=None,
            ruler_detected=True,
            tick_count=len(peaks),
            median_tick_spacing_px=median_spacing,
        )

    refined_median = float(np.median(spacings[inlier_mask]))
    px_per_mm = refined_median / tick_distance_mm

    logger.info(
        "Ruler calibration: %d ticks, median spacing %.1f px, %.2f px/mm",
        len(peaks),
        refined_median,
        px_per_mm,
    )

    return CalibrationResult(
        px_per_mm=px_per_mm,
        ruler_detected=True,
        tick_count=len(peaks),
        median_tick_spacing_px=refined_median,
    )
