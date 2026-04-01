from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class RoleEnum(str, PyEnum):
    ADMINISTRATRICE = "administratrice"
    COORDINATRICE = "coordinatrice"
    RETRANSCRIPTEUR = "retranscripteur"
    CORRECTEUR = "correcteur"
    COMPTABILITE = "comptabilite"
    LECTURE_SEULE = "lecture_seule"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relations
    journal_entries = relationship("JournalActivite", back_populates="utilisateur", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role.value}]>"
