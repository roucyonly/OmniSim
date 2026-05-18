from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(String, ForeignKey("worlds.id"))
    name: Mapped[str] = mapped_column(String)
    tier: Mapped[int] = mapped_column(Integer, default=2)  # 1/2/3
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="idle")  # idle/moving/practicing/sleeping/talking/eating
    personality: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="")
    energy: Mapped[int] = mapped_column(Integer, default=100)
    hunger: Mapped[int] = mapped_column(Integer, default=0)
    hp: Mapped[int] = mapped_column(Integer, default=100)
    attack: Mapped[int] = mapped_column(Integer, default=10)
    defense: Mapped[int] = mapped_column(Integer, default=5)
    speed: Mapped[float] = mapped_column(Float, default=2.0)  # 每tick移动格数
    current_plan_json: Mapped[str] = mapped_column(String, default="[]")
