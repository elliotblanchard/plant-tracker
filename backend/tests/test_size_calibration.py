"""Tests for ruler-based size calibration."""

import numpy as np
import pytest

from app.analysis.size_calibration import CalibrationResult, calibrate_from_ruler


def test_calibrate_horizontal_ruler(ruler_image: tuple[np.ndarray, float]) -> None:
    """Calibration should compute px_per_mm within 20% of the known value."""
    image, expected_px_per_mm = ruler_image
    result = calibrate_from_ruler(image, tick_distance_mm=10.0)

    assert result.ruler_detected is True
    assert result.px_per_mm is not None
    assert result.tick_count >= 3

    # Allow 20% tolerance for the synthetic ruler
    assert abs(result.px_per_mm - expected_px_per_mm) / expected_px_per_mm < 0.20, (
        f"Expected ~{expected_px_per_mm:.2f} px/mm, got {result.px_per_mm:.2f}"
    )


def test_calibrate_blank_image() -> None:
    """Calibration should fail gracefully on a blank image."""
    blank = np.full((100, 400, 3), 200, dtype=np.uint8)
    # Pass explicit roi=[] to disable the default ROI (which would
    # crop this small test image to an empty array)
    result = calibrate_from_ruler(blank, roi=[])
    # May or may not detect ruler, but should not crash
    assert isinstance(result, CalibrationResult)


def test_calibrate_with_roi(ruler_image: tuple[np.ndarray, float]) -> None:
    """Calibration should work when given an explicit ROI."""
    image, expected_px_per_mm = ruler_image
    h, w = image.shape[:2]
    roi = [0, 0, w, h]  # Full image as ROI
    result = calibrate_from_ruler(image, tick_distance_mm=10.0, roi=roi)

    assert result.ruler_detected is True
    assert result.px_per_mm is not None
