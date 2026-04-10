"""Analysis trigger endpoint.

Allows the frontend or a manual call to kick off batch processing.
Supports both legacy Plant_*.jpg images and real camera marchantia_*.jpg images.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analysis.health_score import compute_health_score
from app.analysis.pipeline import analyze_image, analyze_image_multi
from app.auth import verify_token
from app.config import settings
from app.crud import (
    create_image,
    create_measurement,
    get_or_create_plant,
    get_previous_measurement,
)
from app.database import get_db
from app.models import Image
from app.schemas import AnalysisRequest, AnalysisResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analysis"], dependencies=[Depends(verify_token)])


def _is_already_processed(db: Session, source_filename: str, qr_code: str) -> bool:
    """Check if we already have a record for this source file + plant combo."""
    return (
        db.query(Image)
        .join(Image.plant)
        .filter(
            Image.source_filename == source_filename,
        )
        .first()
        is not None
    )


@router.post("/analyze", response_model=AnalysisResult)
def run_analysis(
    request: AnalysisRequest = AnalysisRequest(),
    db: Session = Depends(get_db),
) -> AnalysisResult:
    """Batch-process all images in the configured image directory.

    Handles two filename patterns:
    - ``Plant_*.jpg`` — legacy synthetic images (single plant per image)
    - ``marchantia_*.jpg`` — real camera images (multi-plant per image)
    """
    image_dir = Path(request.image_dir) if request.image_dir else settings.image_dir
    image_dir = image_dir.resolve()

    if not image_dir.is_dir():
        return AnalysisResult(
            images_processed=0,
            plants_found=0,
            errors=[f"Image directory not found: {image_dir}"],
        )

    # Collect images — both legacy and real camera patterns
    patterns = [
        "Plant_*.jpg", "Plant_*.jpeg", "Plant_*.png",
        "plant_*.jpg", "plant_*.jpeg", "plant_*.png",
        "marchantia_*.jpg", "marchantia_*.jpeg",
    ]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(image_dir.glob(pattern))
    files = sorted(set(files), key=lambda p: p.name)

    if not files:
        return AnalysisResult(
            images_processed=0,
            plants_found=0,
            errors=[f"No plant images found in {image_dir}"],
        )

    errors: list[str] = []
    plants_seen: set[str] = set()
    base_time = datetime.now(timezone.utc) - timedelta(hours=len(files))

    for idx, img_path in enumerate(files):
        is_multi = img_path.name.lower().startswith("marchantia_")

        if is_multi:
            # Multi-plant pipeline for real camera images
            results = analyze_image_multi(img_path)
            for result in results:
                if result.errors:
                    errors.extend(result.errors)

                qr_code = result.qr_code or "unknown-plant"
                plants_seen.add(qr_code)

                # Use parsed timestamp from filename, or fall back to sequential
                captured_at = result.captured_at or (base_time + timedelta(hours=idx))

                plant = get_or_create_plant(db, qr_code=qr_code)

                # Growth rate from previous measurement
                prev = get_previous_measurement(db, plant.id, captured_at)
                if prev is not None and prev.measured_at is not None:
                    prev_time = prev.measured_at
                    if prev_time.tzinfo is None:
                        prev_time = prev_time.replace(tzinfo=timezone.utc)
                    delta_hours = (captured_at - prev_time).total_seconds() / 3600.0
                    if delta_hours > 0 and result.area_mm2 is not None and prev.area_mm2 is not None:
                        result.growth_rate = (result.area_mm2 - prev.area_mm2) / delta_hours
                        result.health_score = compute_health_score(
                            greenness_index=result.greenness_index,
                            mean_saturation=result.mean_saturation,
                            growth_rate=result.growth_rate,
                            previous_health=prev.health_score,
                        )

                image_record = create_image(
                    db,
                    plant_id=plant.id,
                    filename=img_path.name,
                    filepath=str(img_path),
                    captured_at=captured_at,
                )
                # Store source_filename for deduplication
                image_record.source_filename = img_path.name
                db.commit()

                create_measurement(
                    db,
                    image_id=image_record.id,
                    plant_id=plant.id,
                    area_px=result.area_px,
                    area_mm2=result.area_mm2,
                    px_per_mm=result.px_per_mm,
                    mean_hue=result.mean_hue,
                    mean_saturation=result.mean_saturation,
                    greenness_index=result.greenness_index,
                    health_score=result.health_score,
                    growth_rate=result.growth_rate,
                    is_overgrown=result.is_overgrown,
                    measured_at=captured_at,
                )
        else:
            # Legacy single-plant pipeline
            captured_at = base_time + timedelta(hours=idx)

            result = analyze_image(img_path)

            if result.errors:
                errors.extend(result.errors)

            qr_code = result.qr_code or "unknown-plant"
            plants_seen.add(qr_code)
            plant = get_or_create_plant(db, qr_code=qr_code)

            # Growth rate from previous measurement
            prev = get_previous_measurement(db, plant.id, captured_at)
            if prev is not None and prev.measured_at is not None:
                prev_time = prev.measured_at
                if prev_time.tzinfo is None:
                    prev_time = prev_time.replace(tzinfo=timezone.utc)
                delta_hours = (captured_at - prev_time).total_seconds() / 3600.0
                if delta_hours > 0 and result.area_mm2 is not None and prev.area_mm2 is not None:
                    result.growth_rate = (result.area_mm2 - prev.area_mm2) / delta_hours
                    result.health_score = compute_health_score(
                        greenness_index=result.greenness_index,
                        mean_saturation=result.mean_saturation,
                        growth_rate=result.growth_rate,
                        previous_health=prev.health_score,
                    )

            image_record = create_image(
                db,
                plant_id=plant.id,
                filename=img_path.name,
                filepath=str(img_path),
                captured_at=captured_at,
            )

            create_measurement(
                db,
                image_id=image_record.id,
                plant_id=plant.id,
                area_px=result.area_px,
                area_mm2=result.area_mm2,
                px_per_mm=result.px_per_mm,
                mean_hue=result.mean_hue,
                mean_saturation=result.mean_saturation,
                greenness_index=result.greenness_index,
                health_score=result.health_score,
                growth_rate=result.growth_rate,
                is_overgrown=result.is_overgrown,
                measured_at=captured_at,
            )

    return AnalysisResult(
        images_processed=len(files),
        plants_found=len(plants_seen),
        errors=errors,
    )
