"""Database CRUD (Create, Read, Update, Delete) helper functions."""

from datetime import datetime

from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from app.models import Image, Measurement, Plant
from app.schemas import PlantSummary


# ── Plants ─────────────────────────────────────────────────────────────


def get_or_create_plant(db: Session, qr_code: str, name: str | None = None) -> Plant:
    """Return existing plant by QR code, or create a new one."""
    plant = db.query(Plant).filter(Plant.qr_code == qr_code).first()
    if plant is None:
        plant = Plant(qr_code=qr_code, name=name)
        db.add(plant)
        db.commit()
        db.refresh(plant)
    return plant


def get_plant(db: Session, plant_id: int) -> Plant | None:
    """Fetch a single plant by primary key, eager-loading images and measurements."""
    return (
        db.query(Plant)
        .options(
            joinedload(Plant.images).joinedload(Image.measurement),
            joinedload(Plant.measurements),
        )
        .filter(Plant.id == plant_id)
        .first()
    )


def list_plants(db: Session) -> list[PlantSummary]:
    """Return all plants with summary statistics from the latest measurement."""
    plants = db.query(Plant).all()
    summaries: list[PlantSummary] = []
    for plant in plants:
        image_count = db.query(func.count(Image.id)).filter(Image.plant_id == plant.id).scalar() or 0
        latest = (
            db.query(Measurement)
            .filter(Measurement.plant_id == plant.id)
            .order_by(desc(Measurement.measured_at))
            .first()
        )
        summaries.append(
            PlantSummary(
                id=plant.id,
                qr_code=plant.qr_code,
                name=plant.name,
                created_at=plant.created_at,
                latest_area_mm2=latest.area_mm2 if latest else None,
                latest_health_score=latest.health_score if latest else None,
                latest_is_overgrown=latest.is_overgrown if latest else None,
                image_count=image_count,
            )
        )
    return summaries


# ── Images ─────────────────────────────────────────────────────────────


def create_image(
    db: Session,
    plant_id: int,
    filename: str,
    filepath: str,
    captured_at: datetime,
) -> Image:
    """Insert a new image record."""
    image = Image(
        plant_id=plant_id,
        filename=filename,
        filepath=filepath,
        captured_at=captured_at,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


def get_image(db: Session, image_id: int) -> Image | None:
    """Fetch a single image by primary key."""
    return db.query(Image).filter(Image.id == image_id).first()


# ── Measurements ───────────────────────────────────────────────────────


def create_measurement(
    db: Session,
    image_id: int,
    plant_id: int,
    area_px: int,
    area_mm2: float | None,
    px_per_mm: float | None,
    mean_hue: float,
    mean_saturation: float,
    greenness_index: float,
    health_score: float,
    growth_rate: float | None,
    is_overgrown: bool,
    measured_at: datetime | None = None,
) -> Measurement:
    """Insert a new measurement record."""
    kwargs: dict = dict(
        image_id=image_id,
        plant_id=plant_id,
        area_px=area_px,
        area_mm2=area_mm2,
        px_per_mm=px_per_mm,
        mean_hue=mean_hue,
        mean_saturation=mean_saturation,
        greenness_index=greenness_index,
        health_score=health_score,
        growth_rate=growth_rate,
        is_overgrown=is_overgrown,
    )
    if measured_at is not None:
        kwargs["measured_at"] = measured_at
    measurement = Measurement(**kwargs)
    db.add(measurement)
    db.commit()
    db.refresh(measurement)
    return measurement


def get_measurements_for_plant(db: Session, plant_id: int) -> list[Measurement]:
    """Return all measurements for a plant, ordered by time ascending."""
    return (
        db.query(Measurement)
        .filter(Measurement.plant_id == plant_id)
        .order_by(Measurement.measured_at)
        .all()
    )


def get_previous_measurement(db: Session, plant_id: int, before: datetime) -> Measurement | None:
    """Return the most recent measurement for a plant before a given time."""
    return (
        db.query(Measurement)
        .filter(Measurement.plant_id == plant_id, Measurement.measured_at < before)
        .order_by(desc(Measurement.measured_at))
        .first()
    )
