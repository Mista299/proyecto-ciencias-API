from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from database import Base

class Taxon(Base):
    __tablename__ = "taxon"

    taxon_id:        Mapped[str] = mapped_column(String, primary_key=True)
    scientific_name: Mapped[str] = mapped_column(String, nullable=False)
    taxon_rank:      Mapped[str | None] = mapped_column(String)
    kingdom:         Mapped[str | None] = mapped_column(String)
    phylum:          Mapped[str | None] = mapped_column(String)
    class_:          Mapped[str | None] = mapped_column(String, name="class")
    order:           Mapped[str | None] = mapped_column(String)
    family:          Mapped[str | None] = mapped_column(String)
    subfamily:       Mapped[str | None] = mapped_column(String)
    genus:           Mapped[str | None] = mapped_column(String)
    specific_epithet: Mapped[str | None] = mapped_column(String)
