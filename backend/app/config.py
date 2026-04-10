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

    # ── Lens distortion calibration ───────────────────────────────────
    # Path to the lens calibration JSON (relative to project_root)
    lens_calibration_file: str = "calibration/lens_calibration.json"
    # Set to False to skip undistortion even when a calibration file exists
    lens_undistort_enabled: bool = True

    # ── Ruler / size calibration ───────────────────────────────────────
    # Known physical distance between ruler tick marks (mm)
    ruler_tick_distance_mm: float = 10.0
    # Optional fixed ROI for the ruler region (x, y, w, h) – None = auto-detect
    # Tuned for 1500x1500 test-plant/01 images: top strip containing ruler ticks
    ruler_roi: list[int] | None = [280, 0, 1220, 160]
    # ArUCO marker ID that anchors the ruler region
    ruler_aruco_id: int = 0
    # Padding offsets (left, top, right, bottom) around ArUCO marker for ruler ROI
    ruler_roi_padding_left: int = 50
    ruler_roi_padding_top: int = 20
    ruler_roi_padding_right: int = 1200
    ruler_roi_padding_bottom: int = 500

    # ── Grey scale calibration ─────────────────────────────────────────
    # ArUCO marker ID that anchors the grey scale strip
    grey_scale_aruco_id: int = 1
    # Padding (px) around the grey scale ArUCO marker to crop the strip
    grey_scale_roi_padding: int = 150

    # ── Plant segmentation ─────────────────────────────────────────────
    # HSV ranges for green-plant masking (PlantCV thresholds)
    hue_lower: int = 25
    hue_upper: int = 95
    saturation_lower: int = 40
    value_lower: int = 40
    # Minimum contour area (pixels) to keep – filters noise
    min_plant_area_px: int = 500
    # Exclusion zones [x, y, w, h] -- areas to zero out before segmentation
    # Tuned for 1500x1500 test-plant/01 images
    exclusion_zones: list[list[int]] = [
        [0, 0, 1500, 380],  # ruler + top gray margin
        [0, 380, 290, 260],  # color chart (left side)
        [0, 1170, 340, 330],  # QR code (bottom-left)
    ]
    # Search radius (px) around each QR code for Hough circle dish detection
    dish_search_radius_px: int = 1000

    # ── Health score weights ───────────────────────────────────────────
    health_weight_greenness: float = 0.4
    health_weight_saturation: float = 0.3
    health_weight_growth: float = 0.3
    # Reference values for "perfectly healthy" normalization
    healthy_greenness_ref: float = 0.45
    healthy_saturation_ref: float = 0.55

    # ── Overgrowth ─────────────────────────────────────────────────────
    overgrowth_threshold_mm2: float = 40000.0

    # ── API ─────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Google Drive sync ──────────────────────────────────────────────
    drive_enabled: bool = False
    drive_folder_id: str = ""
    drive_service_account_json: str = ""
    drive_sync_interval_minutes: int = 60

    # ── Authentication ─────────────────────────────────────────────────
    auth_password: str = ""
    auth_secret_key: str = "plant-tracker-secret-change-me"
    auth_token_expire_days: int = 7


settings = Settings()
