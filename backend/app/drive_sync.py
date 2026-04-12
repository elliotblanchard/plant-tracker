"""Google Drive sync for downloading camera images.

Uses a service account to list and download new images from a shared
Google Drive folder. Skips files already processed (checked via
``Image.source_filename`` in the database).
"""

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.analysis.pipeline import analyze_image_multi
from app.analysis.health_score import compute_health_score
from app.config import settings
from app.crud import (
    create_image,
    create_measurement,
    get_or_create_plant,
    get_previous_measurement,
)
from app.models import Image

logger = logging.getLogger(__name__)


class DriveSync:
    """Download new marchantia images from Google Drive."""

    def __init__(self) -> None:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds_input = settings.drive_service_account_json
        if not creds_input:
            raise ValueError("PT_DRIVE_SERVICE_ACCOUNT_JSON is not set")

        # Debug: log what we received (first 80 chars, redacted)
        safe_preview = creds_input[:80].replace("\n", "\\n") if creds_input else "(empty)"
        logger.warning("DRIVE_CREDS debug: len=%d, starts_with=%r", len(creds_input), safe_preview)

        # Accept: file path, raw JSON string, or base64-encoded JSON
        creds_path = Path(creds_input).expanduser()
        if creds_path.is_file():
            logger.info("Loading credentials from file: %s", creds_path)
            info = json.loads(creds_path.read_text())
        else:
            # Try raw JSON first
            try:
                info = json.loads(creds_input)
                logger.info("Parsed credentials as raw JSON")
            except json.JSONDecodeError as e1:
                logger.warning("Raw JSON parse failed: %s", e1)
                # Try fixing single quotes → double quotes
                try:
                    info = json.loads(creds_input.replace("'", '"'))
                    logger.info("Parsed credentials after quote fix")
                except json.JSONDecodeError as e2:
                    logger.warning("Quote-fix parse failed: %s", e2)
                    # Try base64 decoding
                    import base64
                    try:
                        decoded = base64.b64decode(creds_input).decode("utf-8")
                        logger.warning("Base64 decoded: len=%d, starts_with=%r", len(decoded), decoded[:80])
                        info = json.loads(decoded)
                        logger.info("Parsed credentials from base64")
                    except Exception as e3:
                        logger.error("Base64 decode failed: %s", e3)
                        raise ValueError(
                            "PT_DRIVE_SERVICE_ACCOUNT_JSON is not valid JSON, "
                            "a file path, or base64-encoded JSON. "
                            f"Raw len={len(creds_input)}, preview={safe_preview!r}"
                        )

        credentials = Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        self.service = build("drive", "v3", credentials=credentials)
        self.folder_id = settings.drive_folder_id

    def list_new_images(self) -> list[dict]:
        """List marchantia_*.jpg files in the shared folder."""
        query = (
            f"'{self.folder_id}' in parents "
            "and mimeType='image/jpeg' "
            "and name contains 'marchantia_' "
            "and trashed=false"
        )
        results = (
            self.service.files()
            .list(q=query, fields="files(id, name)", pageSize=100)
            .execute()
        )
        return results.get("files", [])

    def download_image(self, file_id: str, dest: Path) -> Path:
        """Download a single file from Drive to local storage."""
        from googleapiclient.http import MediaIoBaseDownload
        import io

        request = self.service.files().get_media(fileId=file_id)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        logger.info("Downloaded %s to %s", file_id, dest)
        return dest


def sync_and_analyze(db: Session) -> dict:
    """Download new images from Drive and run analysis.

    Returns a summary dict with counts of downloaded/processed/skipped files.
    """
    if not settings.drive_enabled:
        return {"status": "disabled"}

    try:
        drive = DriveSync()
    except Exception as exc:
        logger.exception("Failed to initialize Drive sync: %s", exc)
        return {"status": "error", "message": str(exc)}

    files = drive.list_new_images()
    logger.info("Found %d files in Drive folder", len(files))

    image_dir = Path(settings.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    processed = 0
    skipped = 0

    for file_info in files:
        filename = file_info["name"]

        # Check if already processed
        existing = (
            db.query(Image)
            .filter(Image.source_filename == filename)
            .first()
        )
        if existing:
            skipped += 1
            continue

        # Download
        dest = image_dir / filename
        if not dest.exists():
            try:
                drive.download_image(file_info["id"], dest)
                downloaded += 1
            except Exception as exc:
                logger.exception("Failed to download %s: %s", filename, exc)
                continue

        # Analyze
        try:
            results = analyze_image_multi(dest)
            for result in results:
                qr_code = result.qr_code or "unknown-plant"
                captured_at = result.captured_at

                from datetime import datetime, timezone
                if captured_at is None:
                    captured_at = datetime.now(timezone.utc)

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
                    filename=filename,
                    filepath=str(dest),
                    captured_at=captured_at,
                )
                image_record.source_filename = filename
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

            processed += 1
        except Exception as exc:
            logger.exception("Failed to analyze %s: %s", filename, exc)

    summary = {
        "status": "ok",
        "files_in_drive": len(files),
        "downloaded": downloaded,
        "processed": processed,
        "skipped": skipped,
    }
    logger.info("Drive sync complete: %s", summary)
    return summary
