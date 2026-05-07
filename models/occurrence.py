from sqlalchemy import String, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class Occurrence(Base):
    __tablename__ = "occurrence"

    occurrence_id:    Mapped[str] = mapped_column(String, primary_key=True)
    basis_of_record:  Mapped[str | None] = mapped_column(String)
    institution_code: Mapped[str | None] = mapped_column(String)
    collection_code:  Mapped[str | None] = mapped_column(String)
    catalog_number:   Mapped[str | None] = mapped_column(String)
    occurrence_status: Mapped[str | None] = mapped_column(String)
    disposition:      Mapped[str | None] = mapped_column(String)
    preparations:     Mapped[str | None] = mapped_column(String)
    sex:              Mapped[str | None] = mapped_column(String)
    individual_count: Mapped[int | None] = mapped_column(Integer)
    recorded_by:      Mapped[str | None] = mapped_column(String)
    event_id:         Mapped[str | None] = mapped_column(String, ForeignKey("event.event_id"))
    taxon_id:         Mapped[str | None] = mapped_column(String, ForeignKey("taxon.taxon_id"))
    location_id:      Mapped[str | None] = mapped_column(String, ForeignKey("location.location_id"))
    created_at:       Mapped[object] = mapped_column(DateTime, server_default=func.now())
    updated_at:       Mapped[object] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
