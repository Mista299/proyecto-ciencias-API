from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from database import Base


class User(Base):
    __tablename__ = "user"

    id:              Mapped[str]           = mapped_column(String, primary_key=True)
    username:        Mapped[str]           = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str]           = mapped_column(String, nullable=False)
    role:            Mapped[str]           = mapped_column(String, nullable=False, default="user")
    is_active:       Mapped[bool]          = mapped_column(Boolean, default=True, nullable=False)
    email:           Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    created_at:      Mapped[object]        = mapped_column(DateTime, server_default=func.now())
