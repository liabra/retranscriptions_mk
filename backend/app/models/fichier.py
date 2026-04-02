from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class TypeDocumentEnum(str, PyEnum):
    AUDIO_BRUT = "audio_brut"
    RETRANSCRIPTION_V1 = "retranscription_v1"
    RETRANSCRIPTION_CORRIGEE = "retranscription_corrigee"
    DOCUMENT_PAIEMENT = "document_paiement"
    DOCUMENT_CLIENT = "document_client"
    FACTURE = "facture"
    AUTRE = "autre"


class StatutFichierEnum(str, PyEnum):
    DISPONIBLE = "disponible"
    ARCHIVE = "archive"
    OBSOLETE = "obsolete"


class FichierDossier(Base):
    __tablename__ = "fichiers_dossier"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=False, index=True
    )
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    type_document: Mapped[TypeDocumentEnum] = mapped_column(
        Enum(TypeDocumentEnum), nullable=False
    )
    nom_fichier: Mapped[str] = mapped_column(String(500), nullable=False)
    url_onedrive: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    statut: Mapped[StatutFichierEnum] = mapped_column(
        Enum(StatutFichierEnum), nullable=False, default=StatutFichierEnum.DISPONIBLE
    )
    commentaire: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )

    # Relations
    dossier = relationship("Dossier", back_populates="fichiers")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])

    def __repr__(self) -> str:
        return f"<FichierDossier {self.nom_fichier} [{self.type_document.value}]>"
