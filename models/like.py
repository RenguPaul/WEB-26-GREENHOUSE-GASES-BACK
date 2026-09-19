from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Like(Base):
    __tablename__ = "likes"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        primary_key=True,
    )

    greenhouse_gas_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("greenhouse_gases.id"),
        primary_key=True,
    )