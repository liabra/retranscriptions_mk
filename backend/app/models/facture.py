from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import date
from decimal import Decimal

from sqlalchemy import String, Boolean, Numeric, Date, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class StatutPaiementEnum(str, PyEnum):
    NON_PAYEE = "non_payee"
    PARTIELLEMENT = "partiellement"
    SOLDEE = "soldee"


class FactureClient(Base):
    __tablename__ = "factures_clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_facture: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=False
    )
    payeur_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    calcul_tarifaire_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calculs_tarifaires.id"), nullable=False
    )

    montant_ht: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tva_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    taux_tva: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    montant_tva: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    montant_ttc: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    date_emission: Mapped[date] = mapped_column(Date, nullable=False)
    date_echeance: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    statut_paiement: Mapped[StatutPaiementEnum] = mapped_column(
        Enum(StatutPaiementEnum), default=StatutPaiementEnum.NON_PAYEE, nullable=False
    )

    # Relations
    dossier = relationship("Dossier", foreign_keys=[dossier_id])
    payeur = relationship("Client", foreign_keys=[payeur_id])
    calcul_tarifaire = relationship("CalculTarifaire", foreign_keys=[calcul_tarifaire_id])
