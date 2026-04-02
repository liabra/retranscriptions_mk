from typing import Optional
import uuid
from enum import Enum as PyEnum

from sqlalchemy import String, Boolean, Text, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class TypeClientEnum(str, PyEnum):
    CE = "CE"
    CMAS = "CMAS"
    CSSCT = "CSSCT"
    SYNDICAT = "Syndicat"
    AUTRE = "Autre"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[TypeClientEnum] = mapped_column(Enum(TypeClientEnum), nullable=False)
    entreprise_mere: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_principal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    adresse: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conditions_paiement: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # FK vers GrilleTarifaire (spécifique ou null = grille standard)
    grille_tarifaire_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grilles_tarifaires.id"), nullable=True
    )

    # Relations
    dossiers = relationship("Dossier", foreign_keys="Dossier.client_id", back_populates="client", lazy="dynamic")
    grille_tarifaire = relationship("GrilleTarifaire", foreign_keys=[grille_tarifaire_id])

    def __repr__(self) -> str:
        return f"<Client {self.nom} [{self.type.value}]>"
