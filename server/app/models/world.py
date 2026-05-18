from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class World(Base):
    __tablename__ = "worlds"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="未命名世界")
    grid_size: Mapped[int] = mapped_column(Integer, default=16)
    current_tick: Mapped[int] = mapped_column(Integer, default=0)
    current_day: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="paused")  # running / paused
    theme: Mapped[str] = mapped_column(String, default="custom")
