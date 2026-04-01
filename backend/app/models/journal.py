from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base


class TypeActionEnum(str, PyEnum):
    CREATION = "creation"
    STATUT = "statut"
    AFFECTATION = "affectation"
    ENVOI = "envoi"
    PAIEMENT = "paiement"
    AJUSTEMENT_TARIFAIRE = "ajustement_tarifaire"
    NOTE = "note"
    CONFIG_GRILLE = "config_grille"
    CALCUL_TARIFAIRE = "calcul_tarifaire"
    INCIDENT = "incident"
    ARCHIVAGE = "archivage"
    AUTH = "auth"
    ACCES_DOCUMENT = "acces_document"


class JournalActivite(Base):
    __tablename__ = "journal_activites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    dossier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    utilisateur_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    type_action: Mapped[TypeActionEnum] = mapped_column(Enum(TypeActionEnum), nullable=False, index=True)

    # Données complètes : ancien/nouveau statut, montant avant/après, règle modifiée...
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    ip_source: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Relations
    dossier = relationship("Dossier", back_populates="journal")
    utilisateur = relationship("User", back_populates="journal_entries")

    # Le journal est immuable — pas de update/delete
    __mapper_args__ = {"eager_defaults": False}

    def __repr__(self) -> str:
        return f"<Journal {self.type_action.value} @ {self.timestamp}>"
