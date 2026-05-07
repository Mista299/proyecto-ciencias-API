from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class Identification(Base):
    __tablename__ = "identification"

    identification_id:   Mapped[str] = mapped_column(String, primary_key=True)
    occurrence_id:       Mapped[str | None] = mapped_column(String, ForeignKey("occurrence.occurrence_id"))
    taxon_id:            Mapped[str | None] = mapped_column(String, ForeignKey("taxon.taxon_id"))
    identified_by:       Mapped[str | None] = mapped_column(String)
    date_identified:     Mapped[str | None] = mapped_column(String)
    verification_status: Mapped[str | None] = mapped_column(String)
