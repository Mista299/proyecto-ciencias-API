from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class EmailToken(Base):
    __tablename__ = "email_token"

    id:         Mapped[str]    = mapped_column(String, primary_key=True)
    user_id:    Mapped[str]    = mapped_column(String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    token:      Mapped[str]    = mapped_column(String, unique=True, nullable=False, index=True)
    type:       Mapped[str]    = mapped_column(String, nullable=False)  # "verify" | "reset"
    expires_at: Mapped[object] = mapped_column(DateTime, nullable=False)
    used:       Mapped[bool]   = mapped_column(Boolean, default=False, nullable=False)
