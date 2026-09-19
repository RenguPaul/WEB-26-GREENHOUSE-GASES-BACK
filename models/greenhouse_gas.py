from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class GreenhouseGas(Base):
    __tablename__ = "greenhouse_gases"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    formula: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    global_warming_potential_100y: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    short_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    video_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    concentration_ppm: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    temperature_change_c: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    creator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )