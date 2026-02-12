"""Tests for QR code detection."""

import numpy as np
import pytest

from app.analysis.qr_detection import detect_qr_code


def test_detect_qr_from_synthetic_image(qr_image: tuple[np.ndarray, str]) -> None:
    """QR detector should decode the known text from a synthetic QR image."""
    image, expected_text = qr_image
    result = detect_qr_code(image)
    assert result == expected_text


def test_detect_qr_returns_none_for_blank_image() -> None:
    """QR detector should return None for an image with no QR code."""
    blank = np.full((200, 200, 3), 200, dtype=np.uint8)
    result = detect_qr_code(blank)
    assert result is None


def test_detect_qr_handles_grayscale_gracefully() -> None:
    """QR detector receives a 3-channel image; verify it doesn't crash on edge cases."""
    # Very small image — should not crash
    tiny = np.full((10, 10, 3), 128, dtype=np.uint8)
    result = detect_qr_code(tiny)
    assert result is None
