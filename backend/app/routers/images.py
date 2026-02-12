"""Image-related API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.crud import get_image, get_measurements_for_plant
from app.database import get_db
from app.schemas import ImageOut, MeasurementOut

router = APIRouter(prefix="/api", tags=["images", "measurements"])


@router.get("/images/{image_id}", response_model=ImageOut)
def get_image_meta(image_id: int, db: Session = Depends(get_db)) -> ImageOut:
    """Return metadata for a single image."""
    image = get_image(db, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")
    return ImageOut.model_validate(image)


@router.get("/images/{image_id}/file")
def get_image_file(image_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """Serve the actual image file."""
    image = get_image(db, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")

    filepath = Path(image.filepath)
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"Image file not found on disk: {filepath}")

    media_type = "image/jpeg"
    if filepath.suffix.lower() == ".png":
        media_type = "image/png"

    return FileResponse(str(filepath), media_type=media_type)


@router.get("/plants/{plant_id}/measurements", response_model=list[MeasurementOut])
def get_plant_measurements(plant_id: int, db: Session = Depends(get_db)) -> list[MeasurementOut]:
    """Return all measurements for a plant, ordered chronologically."""
    measurements = get_measurements_for_plant(db, plant_id)
    return [MeasurementOut.model_validate(m) for m in measurements]
