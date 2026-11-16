from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, Enum, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base


class RoleEnum(str, PyEnum):
    ADMINISTRATRICE = "administratrice"
    COORDINATRICE = "coordinatrice"
    RETRANSCRIPTEUR = "retranscripteur"
    CORRECTEUR = "correcteur"          # conservé pour compatibilité, non proposé à la création
    COMPTABILITE = "comptabilite"
    LECTURE_SEULE = "lecture_seule"
    CLIENT = "client"


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

    # Refonte (migration 0005)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    permissions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notif_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # fix: liaison explicite (remplace la correspondance par email)
    prestataire_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestataires.id"), nullable=True, unique=True
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True
    )

    # Relations
    journal_entries = relationship("JournalActivite", back_populates="utilisateur", lazy="dynamic")
    prestataire = relationship("Prestataire", foreign_keys=[prestataire_id])
    client = relationship("Client", foreign_keys=[client_id])

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role.value}]>"
