from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class Location(Base):
    __tablename__ = "location"

    location_id:        Mapped[str] = mapped_column(String, primary_key=True)
    event_id:           Mapped[str | None] = mapped_column(String, ForeignKey("event.event_id"))
    country:            Mapped[str | None] = mapped_column(String)
    state_province:     Mapped[str | None] = mapped_column(String)
    county:             Mapped[str | None] = mapped_column(String)
    municipality:       Mapped[str | None] = mapped_column(String)
    locality:           Mapped[str | None] = mapped_column(String)
    decimal_latitude:   Mapped[float | None] = mapped_column(Float)
    decimal_longitude:  Mapped[float | None] = mapped_column(Float)
    geodetic_datum:     Mapped[str | None] = mapped_column(String)
    minimum_elevation:  Mapped[float | None] = mapped_column(Float)
