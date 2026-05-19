from sqlalchemy import String, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(String, ForeignKey("worlds.id"))
    name: Mapped[str] = mapped_column(String)
    tier: Mapped[int] = mapped_column(Integer, default=2)
    faction: Mapped[str] = mapped_column(String, default="华山派")
    role: Mapped[str] = mapped_column(String, default="")

    # 位置与状态
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    location_name: Mapped[str] = mapped_column(String, default="弟子精舍")
    status: Mapped[str] = mapped_column(String, default="idle")

    # 基础属性
    personality: Mapped[str] = mapped_column(String, default="")
    core_motivation: Mapped[str] = mapped_column(String, default="")
    initial_memory: Mapped[str] = mapped_column(String, default="")
    template: Mapped[str] = mapped_column(String, default="弟子型")
    personality_vector: Mapped[str] = mapped_column(Text, default="")

    # 数值属性 — YAML 维度
    health: Mapped[int] = mapped_column(Integer, default=100)
    inner_power: Mapped[int] = mapped_column(Integer, default=50)
    sword_skill: Mapped[int] = mapped_column(Integer, default=50)

    # 数值属性 — 骰子维度
    talent: Mapped[int] = mapped_column(Integer, default=50)
    wisdom: Mapped[int] = mapped_column(Integer, default=50)
    charisma: Mapped[int] = mapped_column(Integer, default=50)
    perception: Mapped[int] = mapped_column(Integer, default=50)
    luck: Mapped[int] = mapped_column(Integer, default=50)

    # 派生属性
    energy: Mapped[int] = mapped_column(Integer, default=100)
    hunger: Mapped[int] = mapped_column(Integer, default=0)
    speed: Mapped[float] = mapped_column(Float, default=2.0)
