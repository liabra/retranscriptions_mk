from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Text, DateTime, Numeric, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base


class StatutAffectationEnum(str, PyEnum):
    EN_ATTENTE = "en_attente"
    EN_COURS = "en_cours"
    LIVRE = "livre"
    VALIDE = "valide"
    REJETE = "rejete"


class RoleAffectationEnum(str, PyEnum):
    RETRANSCRIPTEUR = "retranscripteur"
    CORRECTEUR = "correcteur"


class Affectation(Base):
    __tablename__ = "affectations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=False
    )
    prestataire_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestataires.id"), nullable=False
    )
    type_role: Mapped[RoleAffectationEnum] = mapped_column(Enum(RoleAffectationEnum), nullable=False)

    date_attribution: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    date_limite_rendu: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    date_rendu_effectif: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    statut: Mapped[StatutAffectationEnum] = mapped_column(
        Enum(StatutAffectationEnum), default=StatutAffectationEnum.EN_ATTENTE, nullable=False
    )

    # Snapshot immuable du tarif prestataire au moment de l'affectation
    grille_snap: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    montant_calcule: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    commentaire: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    dossier = relationship("Dossier", back_populates="affectations")
    prestataire = relationship("Prestataire", back_populates="affectations")
    paiement = relationship("PaiementPrestataire", back_populates="affectation", uselist=False)

    def __repr__(self) -> str:
        return f"<Affectation dossier={self.dossier_id} presta={self.prestataire_id} [{self.type_role.value}]>"
