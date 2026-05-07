from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class Event(Base):
    __tablename__ = "event"

    event_id:          Mapped[str] = mapped_column(String, primary_key=True)
    event_date:        Mapped[str | None] = mapped_column(String)
    year:              Mapped[int | None] = mapped_column(Integer)
    month:             Mapped[int | None] = mapped_column(Integer)
    day:               Mapped[int | None] = mapped_column(Integer)
    habitat:           Mapped[str | None] = mapped_column(String)
    sampling_protocol: Mapped[str | None] = mapped_column(String)
