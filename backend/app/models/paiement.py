from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import date
from decimal import Decimal

from sqlalchemy import String, Text, Numeric, Date, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base


class StatutPaiementPrestaEnum(str, PyEnum):
    A_PAYER = "a_payer"
    VALIDE = "valide"
    PAYE = "paye"


class RolePayeEnum(str, PyEnum):
    RETRANSCRIPTEUR = "retranscripteur"
    CORRECTEUR = "correcteur"


class PaiementPrestataire(Base):
    __tablename__ = "paiements_prestataires"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    affectation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("affectations.id"), nullable=False
    )
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=False
    )
    prestataire_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestataires.id"), nullable=False
    )

    role_paye: Mapped[RolePayeEnum] = mapped_column(Enum(RolePayeEnum), nullable=False)
    nombre_pages: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    # Snapshot complet du calcul : grille, taux, majoration urgence
    detail_calcul: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    montant_brut: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    ajustement_manuel: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    motif_ajustement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    montant_final: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    statut: Mapped[StatutPaiementPrestaEnum] = mapped_column(
        Enum(StatutPaiementPrestaEnum), default=StatutPaiementPrestaEnum.A_PAYER, nullable=False
    )
    date_virement: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reference_virement: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relations
    affectation = relationship("Affectation", back_populates="paiement")
    dossier = relationship("Dossier", foreign_keys=[dossier_id])
    prestataire = relationship("Prestataire", foreign_keys=[prestataire_id])
