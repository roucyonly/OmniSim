from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, ForeignKey("agents.id"), index=True)
    tick: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String)
    importance: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
