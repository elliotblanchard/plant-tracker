"""Plant-related API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import get_plant, list_plants
from app.database import get_db
from app.schemas import PlantDetail, PlantSummary

router = APIRouter(prefix="/api/plants", tags=["plants"])


@router.get("", response_model=list[PlantSummary])
def get_plants(db: Session = Depends(get_db)) -> list[PlantSummary]:
    """List all plants with summary metrics."""
    return list_plants(db)


@router.get("/{plant_id}", response_model=PlantDetail)
def get_plant_detail(plant_id: int, db: Session = Depends(get_db)) -> PlantDetail:
    """Get full details for a single plant including images and measurements."""
    plant = get_plant(db, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail=f"Plant {plant_id} not found")
    return PlantDetail.model_validate(plant)
