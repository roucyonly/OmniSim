from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Reflection(Base):
    __tablename__ = "reflections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, ForeignKey("agents.id"), index=True)
    tick: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(String)
