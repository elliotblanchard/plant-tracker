"""Main analysis pipeline that orchestrates all per-image processing steps.

Call ``analyze_image`` with a file path to run QR detection, ruler calibration,
plant segmentation, color metrics, and health scoring in sequence.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from app.analysis.color_metrics import ColorMetrics, extract_color_metrics
from app.analysis.health_score import compute_health_score, is_overgrown
from app.analysis.qr_detection import detect_qr_code
from app.analysis.segmentation import SegmentationResult, segment_plant
from app.analysis.size_calibration import CalibrationResult, calibrate_from_ruler

logger = logging.getLogger(__name__)


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

    errors: list[str] = field(default_factory=list)


def analyze_image(
    image_path: str | Path,
    previous_area_mm2: float | None = None,
    previous_measured_hours_ago: float | None = None,
    previous_health: float | None = None,
) -> AnalysisOutput:
    """Run the full analysis pipeline on a single image.

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
            output.area_mm2 = output.area_px / (output.px_per_mm ** 2)
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
        output.growth_rate = (output.area_mm2 - previous_area_mm2) / previous_measured_hours_ago

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

    return output
