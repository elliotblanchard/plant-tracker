"""Tests for database CRUD operations."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.crud import (
    create_image,
    create_measurement,
    get_measurements_for_plant,
    get_or_create_plant,
    get_plant,
    get_previous_measurement,
    list_plants,
)
from app.models import Plant


def test_get_or_create_plant_creates_new(db_session: Session) -> None:
    """First call with a QR code should create a new plant."""
    plant = get_or_create_plant(db_session, qr_code="plant-001")
    assert plant.id is not None
    assert plant.qr_code == "plant-001"

    # Second call should return the same plant
    same = get_or_create_plant(db_session, qr_code="plant-001")
    assert same.id == plant.id


def test_create_image_and_measurement(db_session: Session) -> None:
    """Insert an image and associated measurement, then query back."""
    plant = get_or_create_plant(db_session, qr_code="plant-db-test")

    captured = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    image = create_image(
        db_session,
        plant_id=plant.id,
        filename="test.jpg",
        filepath="/tmp/test.jpg",
        captured_at=captured,
    )
    assert image.id is not None
    assert image.plant_id == plant.id

    measurement = create_measurement(
        db_session,
        image_id=image.id,
        plant_id=plant.id,
        area_px=15000,
        area_mm2=120.5,
        px_per_mm=3.5,
        mean_hue=60.0,
        mean_saturation=0.45,
        greenness_index=0.35,
        health_score=78.5,
        growth_rate=None,
        is_overgrown=False,
    )
    assert measurement.id is not None
    assert measurement.area_px == 15000


def test_list_plants_returns_summaries(db_session: Session) -> None:
    """list_plants should return PlantSummary objects for all plants."""
    get_or_create_plant(db_session, qr_code="p1")
    get_or_create_plant(db_session, qr_code="p2")

    summaries = list_plants(db_session)
    assert len(summaries) == 2
    codes = {s.qr_code for s in summaries}
    assert codes == {"p1", "p2"}


def test_get_measurements_for_plant(db_session: Session) -> None:
    """Measurements should be returned in chronological order."""
    plant = get_or_create_plant(db_session, qr_code="plant-series")

    for i in range(3):
        captured = datetime(2025, 6, 1, i, 0, 0, tzinfo=timezone.utc)
        img = create_image(
            db_session,
            plant_id=plant.id,
            filename=f"Plant_{i:02d}.jpg",
            filepath=f"/tmp/Plant_{i:02d}.jpg",
            captured_at=captured,
        )
        create_measurement(
            db_session,
            image_id=img.id,
            plant_id=plant.id,
            area_px=10000 + i * 1000,
            area_mm2=100.0 + i * 10,
            px_per_mm=3.0,
            mean_hue=60.0,
            mean_saturation=0.5,
            greenness_index=0.3,
            health_score=70.0 + i,
            growth_rate=float(i) if i > 0 else None,
            is_overgrown=False,
        )

    measurements = get_measurements_for_plant(db_session, plant.id)
    assert len(measurements) == 3
    # Should be in ascending time order
    assert measurements[0].area_px < measurements[-1].area_px


def test_get_previous_measurement(db_session: Session) -> None:
    """get_previous_measurement should return the most recent measurement before a time."""
    plant = get_or_create_plant(db_session, qr_code="plant-prev")

    for i in range(3):
        captured = datetime(2025, 6, 1, i, 0, 0, tzinfo=timezone.utc)
        img = create_image(
            db_session,
            plant_id=plant.id,
            filename=f"Plant_{i:02d}.jpg",
            filepath=f"/tmp/Plant_{i:02d}.jpg",
            captured_at=captured,
        )
        create_measurement(
            db_session,
            image_id=img.id,
            plant_id=plant.id,
            area_px=10000 + i * 1000,
            area_mm2=100.0 + i * 10,
            px_per_mm=3.0,
            mean_hue=60.0,
            mean_saturation=0.5,
            greenness_index=0.3,
            health_score=70.0,
            growth_rate=None,
            is_overgrown=False,
            measured_at=captured,  # align measured_at with captured_at
        )

    query_time = datetime(2025, 6, 1, 1, 30, 0, tzinfo=timezone.utc)
    prev = get_previous_measurement(db_session, plant.id, query_time)
    assert prev is not None
    assert prev.area_px == 11000  # The i=1 measurement
