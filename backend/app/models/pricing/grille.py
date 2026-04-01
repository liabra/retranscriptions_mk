from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import date, datetime, timezone

from sqlalchemy import String, Boolean, Text, Date, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class TypeGrilleEnum(str, PyEnum):
    CLIENT = "client"
    RETRANSCRIPTEUR = "retranscripteur"
    CORRECTEUR = "correcteur"
    URGENCE = "urgence"
    SNP = "snp"                  # Sans prise de note
    SPECIAL = "special"
    PRISE_DE_NOTE = "prise_de_note"


class CibleGrilleEnum(str, PyEnum):
    GLOBAL = "global"
    CLIENT_SPECIFIQUE = "client_specifique"
    PRESTATAIRE_SPECIFIQUE = "prestataire_specifique"


class GrilleTarifaire(Base):
    """
    Ensemble nommé et versionné de règles tarifaires.
    Principe cardinal : aucune valeur n'est codée en dur — tout passe par ce modèle.
    """
    __tablename__ = "grilles_tarifaires"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[TypeGrilleEnum] = mapped_column(Enum(TypeGrilleEnum), nullable=False, index=True)
    cible: Mapped[CibleGrilleEnum] = mapped_column(
        Enum(CibleGrilleEnum), default=CibleGrilleEnum.GLOBAL, nullable=False
    )
    # ID du client ou prestataire si cible spécifique
    cible_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # null = active indéfiniment
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    creee_par_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    date_creation: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relations
    regles = relationship("RegleTarifaire", back_populates="grille", lazy="dynamic",
                          cascade="all, delete-orphan")
    creee_par = relationship("User", foreign_keys=[creee_par_id])

    def __repr__(self) -> str:
        return f"<GrilleTarifaire {self.nom} v{self.version} [{self.type.value}]>"
