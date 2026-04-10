"""Main analysis pipeline that orchestrates all per-image processing steps.

Call ``analyze_image`` with a file path to run lens undistortion, QR detection,
ruler calibration, plant segmentation, color metrics, and health scoring in
sequence.

``analyze_image_multi`` extends this for multi-plant images: it uses ArUCO
markers, multi-QR detection, grey scale calibration, and per-plant
segmentation to return one ``AnalysisOutput`` per plant in the image.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from app.analysis.aruco_detection import detect_aruco_markers
from app.analysis.color_metrics import ColorMetrics, extract_color_metrics
from app.analysis.grey_scale_calibration import (
    apply_brightness_correction,
    calibrate_from_grey_scale,
)
from app.analysis.health_score import compute_health_score, is_overgrown
from app.analysis.lens_calibration import LensCalibration, load_calibration
from app.analysis.qr_detection import detect_all_qr_codes, detect_qr_code
from app.analysis.segmentation import (
    SegmentationResult,
    segment_plant,
    segment_plants,
)
from app.analysis.size_calibration import CalibrationResult, calibrate_from_ruler
from app.config import settings

logger = logging.getLogger(__name__)

# Load lens calibration once at module import time.
_lens_calibration: LensCalibration | None = None
if settings.lens_undistort_enabled:
    _cal_path = settings.project_root / settings.lens_calibration_file
    _lens_calibration = load_calibration(_cal_path)
    if _lens_calibration is None:
        logger.info(
            "No lens calibration found at %s — images will NOT be undistorted. "
            "Run 'python -m scripts.calibrate_lens' to generate one.",
            _cal_path,
        )

# Regex for parsing timestamps from camera filenames: marchantia_YYYYMMDD_HHMMSS.jpg
_FILENAME_TS_RE = re.compile(r"marchantia_(\d{8})_(\d{6})", re.IGNORECASE)


@dataclass
class AnalysisOutput:
    """Complete result from processing a single image."""

    filepath: str
    filename: str

    # QR
    qr_code: str | None = None

    # Calibration
    px_per_mm: float | None = None
    ruler_detected: bool = False

    # Segmentation
    area_px: int = 0
    area_mm2: float | None = None
    segmentation_success: bool = False

    # Color
    mean_hue: float = 0.0
    mean_saturation: float = 0.0
    greenness_index: float = 0.0

    # Health
    health_score: float = 0.0
    growth_rate: float | None = None
    is_overgrown: bool = False

    # Timestamp parsed from filename (real camera images)
    captured_at: datetime | None = None

    errors: list[str] = field(default_factory=list)


def _parse_captured_at(filename: str) -> datetime | None:
    """Parse capture timestamp from camera filename pattern.

    Expects: ``marchantia_YYYYMMDD_HHMMSS.jpg``
    """
    match = _FILENAME_TS_RE.search(filename)
    if not match:
        return None
    date_str, time_str = match.group(1), match.group(2)
    try:
        return datetime.strptime(
            f"{date_str}_{time_str}", "%Y%m%d_%H%M%S"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _undistort(image: np.ndarray) -> np.ndarray:
    """Apply lens undistortion if calibration is loaded."""
    if _lens_calibration is not None:
        image = _lens_calibration.undistort(image)
        logger.debug("Applied lens undistortion")
    return image


def analyze_image(
    image_path: str | Path,
    previous_area_mm2: float | None = None,
    previous_measured_hours_ago: float | None = None,
    previous_health: float | None = None,
) -> AnalysisOutput:
    """Run the full analysis pipeline on a single image (backward compatible).

    Args:
        image_path: Path to the image file.
        previous_area_mm2: Area from the prior measurement (for growth rate).
        previous_measured_hours_ago: Time since previous measurement in hours.
        previous_health: Previous health score (for growth component fallback).

    Returns:
        ``AnalysisOutput`` with all metrics populated.
    """
    image_path = Path(image_path)
    output = AnalysisOutput(filepath=str(image_path), filename=image_path.name)

    # Load image
    image = cv2.imread(str(image_path))
    if image is None:
        output.errors.append(f"Failed to read image: {image_path}")
        logger.error("Cannot read image: %s", image_path)
        return output

    logger.info("Analyzing image: %s", image_path.name)

    # 0. Lens undistortion
    image = _undistort(image)

    # 1. QR code
    try:
        output.qr_code = detect_qr_code(image)
    except Exception as exc:
        msg = f"QR detection error: {exc}"
        output.errors.append(msg)
        logger.exception(msg)

    # 2. Ruler calibration
    try:
        cal: CalibrationResult = calibrate_from_ruler(image)
        output.px_per_mm = cal.px_per_mm
        output.ruler_detected = cal.ruler_detected
    except Exception as exc:
        msg = f"Ruler calibration error: {exc}"
        output.errors.append(msg)
        logger.exception(msg)

    # 3. Plant segmentation
    seg: SegmentationResult | None = None
    try:
        seg = segment_plant(image)
        output.area_px = seg.area_px
        output.segmentation_success = seg.success

        if seg.success and output.px_per_mm is not None and output.px_per_mm > 0:
            output.area_mm2 = output.area_px / (output.px_per_mm**2)
    except Exception as exc:
        msg = f"Segmentation error: {exc}"
        output.errors.append(msg)
        logger.exception(msg)

    # 4. Color metrics (only if segmentation succeeded)
    if output.segmentation_success and seg is not None:
        try:
            colors: ColorMetrics = extract_color_metrics(image, seg.mask)
            output.mean_hue = colors.mean_hue
            output.mean_saturation = colors.mean_saturation
            output.greenness_index = colors.greenness_index
        except Exception as exc:
            msg = f"Color metrics error: {exc}"
            output.errors.append(msg)
            logger.exception(msg)

    # 5. Growth rate
    if (
        previous_area_mm2 is not None
        and previous_measured_hours_ago is not None
        and previous_measured_hours_ago > 0
        and output.area_mm2 is not None
    ):
        output.growth_rate = (
            output.area_mm2 - previous_area_mm2
        ) / previous_measured_hours_ago

    # 6. Health score
    try:
        output.health_score = compute_health_score(
            greenness_index=output.greenness_index,
            mean_saturation=output.mean_saturation,
            growth_rate=output.growth_rate,
            previous_health=previous_health,
        )
    except Exception as exc:
        msg = f"Health score error: {exc}"
        output.errors.append(msg)
        logger.exception(msg)

    # 7. Overgrowth flag
    output.is_overgrown = is_overgrown(output.area_mm2)

    # 8. Timestamp from filename
    output.captured_at = _parse_captured_at(image_path.name)

    return output


def analyze_image_multi(
    image_path: str | Path,
) -> list[AnalysisOutput]:
    """Run the multi-plant analysis pipeline on a single camera image.

    Steps:
    1. Load + lens undistort
    2. Detect ArUCO markers
    3. Detect all QR codes
    4. Ruler calibration (ArUCO-anchored)
    5. Grey scale calibration + brightness correction
    6. Per-plant segmentation
    7. Per-plant color metrics + health score

    Args:
        image_path: Path to the camera image file.

    Returns:
        List of ``AnalysisOutput``, one per detected plant.
    """
    image_path = Path(image_path)
    captured_at = _parse_captured_at(image_path.name)

    image = cv2.imread(str(image_path))
    if image is None:
        return [AnalysisOutput(
            filepath=str(image_path),
            filename=image_path.name,
            errors=[f"Failed to read image: {image_path}"],
        )]

    logger.info("Multi-plant analysis: %s (%dx%d)", image_path.name, image.shape[1], image.shape[0])

    # 1. Lens undistortion
    image = _undistort(image)

    # 2. ArUCO markers
    try:
        markers = detect_aruco_markers(image)
    except Exception as exc:
        logger.exception("ArUCO detection error: %s", exc)
        markers = []

    # 3. QR codes
    try:
        qr_results = detect_all_qr_codes(image)
    except Exception as exc:
        logger.exception("Multi-QR detection error: %s", exc)
        qr_results = []

    # 4. Ruler calibration (shared across all plants)
    px_per_mm: float | None = None
    ruler_detected = False
    try:
        cal = calibrate_from_ruler(image, aruco_markers=markers)
        px_per_mm = cal.px_per_mm
        ruler_detected = cal.ruler_detected
    except Exception as exc:
        logger.exception("Ruler calibration error: %s", exc)

    # 5. Grey scale calibration + brightness correction
    try:
        grey_cal = calibrate_from_grey_scale(image, aruco_markers=markers)
        image = apply_brightness_correction(image, grey_cal)
    except Exception as exc:
        logger.exception("Grey scale calibration error: %s", exc)

    # 6. Per-plant segmentation
    try:
        seg_results = segment_plants(image, qr_results, aruco_markers=markers)
    except Exception as exc:
        logger.exception("Multi-plant segmentation error: %s", exc)
        seg_results = []

    if not seg_results:
        return [AnalysisOutput(
            filepath=str(image_path),
            filename=image_path.name,
            errors=["No plants segmented"],
            captured_at=captured_at,
        )]

    # 7. Per-plant metrics
    outputs: list[AnalysisOutput] = []
    for seg in seg_results:
        output = AnalysisOutput(
            filepath=str(image_path),
            filename=image_path.name,
            qr_code=seg.qr_code or None,
            px_per_mm=px_per_mm,
            ruler_detected=ruler_detected,
            area_px=seg.area_px,
            segmentation_success=seg.success,
            captured_at=captured_at,
        )

        # Area in mm²
        if seg.success and px_per_mm is not None and px_per_mm > 0:
            output.area_mm2 = seg.area_px / (px_per_mm**2)

        # Color metrics
        if seg.success:
            try:
                colors = extract_color_metrics(image, seg.mask)
                output.mean_hue = colors.mean_hue
                output.mean_saturation = colors.mean_saturation
                output.greenness_index = colors.greenness_index
            except Exception as exc:
                output.errors.append(f"Color metrics error: {exc}")

        # Health score
        try:
            output.health_score = compute_health_score(
                greenness_index=output.greenness_index,
                mean_saturation=output.mean_saturation,
                growth_rate=None,
                previous_health=None,
            )
        except Exception as exc:
            output.errors.append(f"Health score error: {exc}")

        # Overgrowth
        output.is_overgrown = is_overgrown(output.area_mm2)

        outputs.append(output)

    logger.info("Multi-plant analysis complete: %d plants from %s", len(outputs), image_path.name)
    return outputs
