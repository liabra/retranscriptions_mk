from typing import Optional
import uuid
from enum import Enum as PyEnum
from decimal import Decimal

from sqlalchemy import String, Boolean, Integer, Numeric, Text, Enum, ForeignKey, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class RolePrestaEnum(str, PyEnum):
    RETRANSCRIPTEUR = "retranscripteur"
    CORRECTEUR = "correcteur"
    LES_DEUX = "les_deux"


class Prestataire(Base):
    __tablename__ = "prestataires"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RolePrestaEnum] = mapped_column(Enum(RolePrestaEnum), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    telephone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    disponible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    charge_actuelle: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note_qualite: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.00"), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # IBAN chiffré AES-256
    iban_chiffre: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # FK vers GrilleTarifaire spécifique à ce prestataire
    grille_tarifaire_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grilles_tarifaires.id"), nullable=True
    )

    # Relations
    affectations = relationship("Affectation", back_populates="prestataire", lazy="dynamic")
    grille_tarifaire = relationship("GrilleTarifaire", foreign_keys=[grille_tarifaire_id])

    def __repr__(self) -> str:
        return f"<Prestataire {self.nom} [{self.role.value}]>"
