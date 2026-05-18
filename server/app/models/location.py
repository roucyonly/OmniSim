from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(String, ForeignKey("worlds.id"))
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    terrain: Mapped[str] = mapped_column(String, default="plain")  # plain/mountain/forest/water/building
    name: Mapped[str] = mapped_column(String, nullable=True)
    building_type: Mapped[str] = mapped_column(String, nullable=True)  # 练剑场/食堂/宿舍/...
