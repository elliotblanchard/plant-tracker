"""Tests for plant segmentation."""

import cv2
import numpy as np
import pytest

from app.analysis.segmentation import segment_plant


def test_segment_green_plant(green_plant_image: np.ndarray) -> None:
    """Segmentation should detect the green circle as plant tissue."""
    result = segment_plant(green_plant_image)

    assert result.success is True
    assert result.area_px > 0

    # The synthetic circle has area ~ pi*80^2 ≈ 20106 px.
    # Allow a generous range for thresholding differences.
    assert 5000 < result.area_px < 40000, f"Unexpected area: {result.area_px}"

    # Mask should have nonzero pixels
    assert cv2.countNonZero(result.mask) == result.area_px


def test_segment_blank_image() -> None:
    """Segmentation on a uniform image should return a low/zero area."""
    blank = np.full((200, 300, 3), 200, dtype=np.uint8)
    result = segment_plant(blank)
    # May or may not "succeed", but area should be very small
    assert result.area_px < 500


def test_segment_returns_contour(green_plant_image: np.ndarray) -> None:
    """Successful segmentation should include the largest contour."""
    result = segment_plant(green_plant_image)
    assert result.success is True
    assert result.contour is not None
    assert len(result.contour) > 0
