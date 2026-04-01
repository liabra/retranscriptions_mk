from typing import Optional
import uuid
from enum import Enum as PyEnum
from decimal import Decimal

from sqlalchemy import Text, Boolean, Numeric, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class GraviteEnum(str, PyEnum):
    MINEUR = "mineur"
    MAJEUR = "majeur"
    BLOQUANT = "bloquant"


class StatutIncidentEnum(str, PyEnum):
    OUVERT = "ouvert"
    EN_COURS = "en_cours"
    RESOLU = "resolu"


class IncidentQualite(Base):
    __tablename__ = "incidents_qualite"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=False
    )
    signale_par_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    prestataire_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prestataires.id"), nullable=True
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    gravite: Mapped[GraviteEnum] = mapped_column(Enum(GraviteEnum), nullable=False)
    statut: Mapped[StatutIncidentEnum] = mapped_column(
        Enum(StatutIncidentEnum), default=StatutIncidentEnum.OUVERT, nullable=False
    )

    impact_tarifaire: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    montant_impact: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    dossier = relationship("Dossier", back_populates="incidents")
    signale_par = relationship("User", foreign_keys=[signale_par_id])
    prestataire = relationship("Prestataire", foreign_keys=[prestataire_id])
