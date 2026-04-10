"""Grey scale calibration using Kodak Gray Scale strip.

Uses ArUCO marker 1 to locate the grey scale strip, samples known
grey patches, and derives a linear brightness correction (gain + offset).
Non-blocking: if the strip is not found, the pipeline continues without
correction.
"""

import logging
from dataclasses import dataclass

import cv2
import numpy as np

from app.analysis.aruco_detection import ArucoMarker, get_marker_by_id
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class GreyScaleCalibration:
    """Result of the grey scale calibration step."""

    brightness_offset: float = 0.0
    contrast_factor: float = 1.0
    detected: bool = False


def calibrate_from_grey_scale(
    image: np.ndarray,
    aruco_markers: list[ArucoMarker] | None = None,
) -> GreyScaleCalibration:
    """Derive brightness/contrast correction from the Kodak Gray Scale strip.

    Uses ArUCO marker 1 (configurable via ``settings.grey_scale_aruco_id``)
    to locate the strip region. Samples expected grey patches (white → black
    gradient) and computes a linear correction.

    Args:
        image: BGR image (NumPy array).
        aruco_markers: Pre-detected ArUCO markers (avoids re-detection).

    Returns:
        ``GreyScaleCalibration`` with correction parameters.
    """
    if aruco_markers is None:
        return GreyScaleCalibration()

    marker = get_marker_by_id(aruco_markers, settings.grey_scale_aruco_id)
    if marker is None:
        logger.info("Grey scale ArUCO marker %d not found — skipping calibration", settings.grey_scale_aruco_id)
        return GreyScaleCalibration()

    h, w = image.shape[:2]
    cx, cy = marker.center
    pad = settings.grey_scale_roi_padding

    x1 = max(0, cx - pad)
    y1 = max(0, cy - pad)
    x2 = min(w, cx + pad)
    y2 = min(h, cy + pad * 3)  # strip extends below marker

    roi = image[y1:y2, x1:x2]
    if roi.size == 0:
        logger.warning("Grey scale ROI is empty")
        return GreyScaleCalibration()

    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # Sample patches along the strip (top = lightest, bottom = darkest)
    strip_h = gray_roi.shape[0]
    num_patches = 5
    patch_height = strip_h // num_patches

    measured_values: list[float] = []
    for i in range(num_patches):
        patch = gray_roi[i * patch_height : (i + 1) * patch_height, :]
        if patch.size > 0:
            measured_values.append(float(np.mean(patch)))

    if len(measured_values) < 3:
        logger.warning("Too few grey scale patches detected (%d)", len(measured_values))
        return GreyScaleCalibration()

    # Expected values: linear gradient from ~230 (white) to ~30 (black)
    expected_values = np.linspace(230, 30, len(measured_values))
    measured_arr = np.array(measured_values)

    # Least-squares fit: expected = gain * measured + offset
    A = np.vstack([measured_arr, np.ones(len(measured_arr))]).T
    result = np.linalg.lstsq(A, expected_values, rcond=None)
    gain, offset = result[0]

    logger.info("Grey scale calibration: gain=%.3f, offset=%.1f", gain, offset)
    return GreyScaleCalibration(
        brightness_offset=float(offset),
        contrast_factor=float(gain),
        detected=True,
    )


def apply_brightness_correction(
    image: np.ndarray,
    calibration: GreyScaleCalibration,
) -> np.ndarray:
    """Apply the brightness/contrast correction to the image.

    Args:
        image: BGR image (NumPy array).
        calibration: Correction parameters from ``calibrate_from_grey_scale``.

    Returns:
        Corrected BGR image (same shape and dtype as input).
    """
    if not calibration.detected:
        return image

    corrected = cv2.convertScaleAbs(
        image,
        alpha=calibration.contrast_factor,
        beta=calibration.brightness_offset,
    )
    logger.debug("Applied brightness correction (gain=%.3f, offset=%.1f)",
                 calibration.contrast_factor, calibration.brightness_offset)
    return corrected
