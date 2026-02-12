"""SQLAlchemy ORM models for plants, images, and measurements."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Plant(Base):
    """A single Marchantia plant, identified by its QR code."""

    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    qr_code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    images: Mapped[list["Image"]] = relationship(back_populates="plant", cascade="all, delete-orphan")
    measurements: Mapped[list["Measurement"]] = relationship(back_populates="plant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Plant id={self.id} qr_code={self.qr_code!r}>"


class Image(Base):
    """A single time-stamped photograph of a plant."""

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plant_id: Mapped[int] = mapped_column(Integer, ForeignKey("plants.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    filepath: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    plant: Mapped["Plant"] = relationship(back_populates="images")
    measurement: Mapped["Measurement | None"] = relationship(back_populates="image", uselist=False)

    def __repr__(self) -> str:
        return f"<Image id={self.id} filename={self.filename!r}>"


class Measurement(Base):
    """Per-image analysis results: area, color metrics, health score, etc."""

    __tablename__ = "measurements"
    __table_args__ = (UniqueConstraint("image_id", name="uq_measurement_image"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[int] = mapped_column(Integer, ForeignKey("images.id"), nullable=False, index=True)
    plant_id: Mapped[int] = mapped_column(Integer, ForeignKey("plants.id"), nullable=False, index=True)

    # Area
    area_px: Mapped[int] = mapped_column(Integer, nullable=False)
    area_mm2: Mapped[float | None] = mapped_column(Float, nullable=True)
    px_per_mm: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Color metrics
    mean_hue: Mapped[float] = mapped_column(Float, nullable=False)
    mean_saturation: Mapped[float] = mapped_column(Float, nullable=False)
    greenness_index: Mapped[float] = mapped_column(Float, nullable=False)

    # Derived scores
    health_score: Mapped[float] = mapped_column(Float, nullable=False)
    growth_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_overgrown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    image: Mapped["Image"] = relationship(back_populates="measurement")
    plant: Mapped["Plant"] = relationship(back_populates="measurements")

    def __repr__(self) -> str:
        return f"<Measurement id={self.id} area_px={self.area_px} health={self.health_score:.1f}>"
