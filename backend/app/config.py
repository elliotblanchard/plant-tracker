"""Application configuration using Pydantic Settings.

All tunable thresholds, paths, and weights live here.
Override via environment variables prefixed with PT_ (e.g. PT_OVERGROWTH_THRESHOLD_MM2=500).
"""

from pathlib import Path
from pydantic_settings import BaseSettings


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # Plant_Tracker/


class Settings(BaseSettings):
    """Central configuration for the Plant Tracker application."""

    model_config = {"env_prefix": "PT_"}

    # ── Paths ──────────────────────────────────────────────────────────
    project_root: Path = _PROJECT_ROOT
    image_dir: Path = _PROJECT_ROOT / "test-plant"
    database_url: str = f"sqlite:///{_PROJECT_ROOT / 'data' / 'plant_tracker.db'}"

    # ── Ruler / size calibration ───────────────────────────────────────
    # Known physical distance between major tick marks (mm)
    ruler_tick_distance_mm: float = 10.0
    # Optional fixed ROI for the ruler region (x, y, w, h) – None = auto-detect
    ruler_roi: list[int] | None = None

    # ── Plant segmentation ─────────────────────────────────────────────
    # HSV ranges for green-plant masking (PlantCV thresholds)
    hue_lower: int = 25
    hue_upper: int = 95
    saturation_lower: int = 40
    value_lower: int = 40
    # Minimum contour area (pixels) to keep – filters noise
    min_plant_area_px: int = 500

    # ── Health score weights ───────────────────────────────────────────
    health_weight_greenness: float = 0.4
    health_weight_saturation: float = 0.3
    health_weight_growth: float = 0.3
    # Reference values for "perfectly healthy" normalization
    healthy_greenness_ref: float = 0.45
    healthy_saturation_ref: float = 0.55

    # ── Overgrowth ─────────────────────────────────────────────────────
    overgrowth_threshold_mm2: float = 400.0

    # ── API ─────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()
