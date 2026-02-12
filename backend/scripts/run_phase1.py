#!/usr/bin/env python3
"""CLI batch-processing script for Phase 1.

Processes all Plant_*.jpg images in a directory, runs the analysis pipeline,
and stores results in the SQLite database.

Usage:
    python scripts/run_phase1.py --image-dir ../test-plant
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure the backend package is importable when running from the scripts/ dir
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis.pipeline import analyze_image
from app.config import settings
from app.crud import (
    create_image,
    create_measurement,
    get_or_create_plant,
    get_previous_measurement,
)
from app.database import SessionLocal, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def collect_images(image_dir: Path) -> list[Path]:
    """Glob for plant images and return them sorted by filename (chronological)."""
    patterns = ["Plant_*.jpg", "Plant_*.jpeg", "Plant_*.png", "plant_*.jpg", "plant_*.jpeg", "plant_*.png"]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(image_dir.glob(pattern))
    # Deduplicate and sort by name
    files = sorted(set(files), key=lambda p: p.name)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 1 analysis pipeline on plant images.")
    parser.add_argument(
        "--image-dir",
        type=str,
        default=str(settings.image_dir),
        help="Directory containing plant images (default: %(default)s)",
    )
    args = parser.parse_args()

    image_dir = Path(args.image_dir).resolve()
    if not image_dir.is_dir():
        logger.error("Image directory does not exist: %s", image_dir)
        sys.exit(1)

    images = collect_images(image_dir)
    if not images:
        logger.error("No plant images found in %s", image_dir)
        sys.exit(1)

    logger.info("Found %d images in %s", len(images), image_dir)

    # Ensure DB tables exist
    init_db()
    db = SessionLocal()

    errors: list[str] = []
    plants_seen: set[str] = set()

    # Assign synthetic timestamps: one hour apart, starting now minus N hours
    base_time = datetime.now(timezone.utc) - timedelta(hours=len(images))

    try:
        for idx, img_path in enumerate(images):
            captured_at = base_time + timedelta(hours=idx)
            logger.info("─── [%d/%d] %s ───", idx + 1, len(images), img_path.name)

            # Look up the previous measurement context for growth rate
            previous_area_mm2 = None
            previous_hours_ago = None
            previous_health = None

            # Run the analysis pipeline
            result = analyze_image(
                img_path,
                previous_area_mm2=previous_area_mm2,
                previous_measured_hours_ago=previous_hours_ago,
                previous_health=previous_health,
            )

            if result.errors:
                errors.extend(result.errors)

            # Determine plant identity
            qr_code = result.qr_code or "unknown-plant"
            plants_seen.add(qr_code)
            plant = get_or_create_plant(db, qr_code=qr_code)

            # Now that we have the plant, look up previous measurement for growth
            prev = get_previous_measurement(db, plant.id, captured_at)
            if prev is not None and prev.measured_at is not None:
                delta_hours = (captured_at - prev.measured_at).total_seconds() / 3600.0
                if delta_hours > 0 and result.area_mm2 is not None and prev.area_mm2 is not None:
                    result.growth_rate = (result.area_mm2 - prev.area_mm2) / delta_hours
                    previous_health = prev.health_score
                    # Recompute health with growth rate
                    from app.analysis.health_score import compute_health_score

                    result.health_score = compute_health_score(
                        greenness_index=result.greenness_index,
                        mean_saturation=result.mean_saturation,
                        growth_rate=result.growth_rate,
                        previous_health=previous_health,
                    )

            # Store image record
            image_record = create_image(
                db,
                plant_id=plant.id,
                filename=img_path.name,
                filepath=str(img_path),
                captured_at=captured_at,
            )

            # Store measurement
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
            )

            logger.info(
                "  → area=%d px  area_mm2=%s  health=%.1f  overgrown=%s  qr=%s",
                result.area_px,
                f"{result.area_mm2:.1f}" if result.area_mm2 else "N/A",
                result.health_score,
                result.is_overgrown,
                qr_code,
            )

    finally:
        db.close()

    # ── Summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"  Images processed : {len(images)}")
    print(f"  Plants found     : {len(plants_seen)} ({', '.join(sorted(plants_seen))})")
    print(f"  Errors           : {len(errors)}")
    if errors:
        for err in errors:
            print(f"    ⚠  {err}")
    print(f"  Database         : {settings.database_url}")
    print("=" * 60)


if __name__ == "__main__":
    main()
