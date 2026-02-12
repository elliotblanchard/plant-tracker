"""Pydantic schemas for API request / response serialization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Measurement ────────────────────────────────────────────────────────


class MeasurementOut(BaseModel):
    """Single measurement returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    image_id: int
    plant_id: int
    area_px: int
    area_mm2: float | None
    px_per_mm: float | None
    mean_hue: float
    mean_saturation: float
    greenness_index: float
    health_score: float
    growth_rate: float | None
    is_overgrown: bool
    measured_at: datetime


# ── Image ──────────────────────────────────────────────────────────────


class ImageOut(BaseModel):
    """Image metadata returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    filename: str
    filepath: str
    captured_at: datetime
    uploaded_at: datetime
    measurement: MeasurementOut | None = None


# ── Plant ──────────────────────────────────────────────────────────────


class PlantSummary(BaseModel):
    """Lightweight plant record for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    qr_code: str
    name: str | None
    created_at: datetime
    latest_area_mm2: float | None = None
    latest_health_score: float | None = None
    latest_is_overgrown: bool | None = None
    image_count: int = 0


class PlantDetail(BaseModel):
    """Full plant record including all images and measurements."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    qr_code: str
    name: str | None
    created_at: datetime
    images: list[ImageOut] = []
    measurements: list[MeasurementOut] = []


# ── Analysis trigger ───────────────────────────────────────────────────


class AnalysisRequest(BaseModel):
    """Request body for the /analyze endpoint."""

    image_dir: str | None = None  # Defaults to config.image_dir


class AnalysisResult(BaseModel):
    """Summary returned after a batch analysis run."""

    images_processed: int
    plants_found: int
    errors: list[str] = []
