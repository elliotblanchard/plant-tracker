"""Shared pytest fixtures for the Plant Tracker test suite."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import cv2
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Provide a clean, in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def green_plant_image() -> np.ndarray:
    """Create a synthetic BGR image with a green 'plant' on a white background.

    The plant is a filled green circle in the center.
    """
    h, w = 480, 640
    image = np.full((h, w, 3), 240, dtype=np.uint8)  # light gray background

    # Draw a green circle (simulates plant tissue)
    center = (w // 2, h // 2)
    radius = 80
    cv2.circle(image, center, radius, (30, 140, 40), thickness=-1)  # BGR green

    return image


@pytest.fixture()
def qr_image(tmp_path: Path) -> tuple[np.ndarray, str]:
    """Create a synthetic image containing a QR code encoding 'plant-test-001'.

    Uses OpenCV's QRCodeEncoder to generate the QR, then embeds it on a white
    canvas.  Returns (image, expected_decoded_string).
    """
    qr_text = "plant-test-001"

    # Generate QR code
    encoder = cv2.QRCodeEncoder.create()
    qr_img = encoder.encode(qr_text)

    # Place on a larger canvas
    canvas_h, canvas_w = 400, 400
    canvas = np.full((canvas_h, canvas_w, 3), 255, dtype=np.uint8)

    qr_h, qr_w = qr_img.shape[:2]
    # Scale QR to ~150px
    scale = 150 / max(qr_h, qr_w)
    qr_resized = cv2.resize(qr_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    rh, rw = qr_resized.shape[:2]

    y_off = (canvas_h - rh) // 2
    x_off = (canvas_w - rw) // 2

    if len(qr_resized.shape) == 2:
        qr_resized = cv2.cvtColor(qr_resized, cv2.COLOR_GRAY2BGR)

    canvas[y_off : y_off + rh, x_off : x_off + rw] = qr_resized

    return canvas, qr_text


@pytest.fixture()
def ruler_image() -> tuple[np.ndarray, float]:
    """Create a synthetic ruler image with known tick spacing.

    Draws a horizontal ruler with ticks every 30 pixels.
    Known physical tick distance = 10mm => expected px_per_mm = 3.0.

    Returns (image, expected_px_per_mm).
    """
    h, w = 100, 600
    image = np.full((h, w, 3), 240, dtype=np.uint8)  # gray background

    tick_spacing_px = 30
    tick_distance_mm = 10.0
    expected_px_per_mm = tick_spacing_px / tick_distance_mm  # 3.0

    # Draw ruler baseline
    y_base = h // 2
    cv2.line(image, (20, y_base), (w - 20, y_base), (0, 0, 0), 2)

    # Draw tick marks
    x = 20
    while x < w - 20:
        cv2.line(image, (x, y_base - 15), (x, y_base + 15), (0, 0, 0), 2)
        x += tick_spacing_px

    return image, expected_px_per_mm
