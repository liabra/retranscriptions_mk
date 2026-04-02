from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import String, Integer, Numeric, Text, Date, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base


class StatutDossierEnum(str, PyEnum):
    RECU = "recu"
    EN_QUALIFICATION = "en_qualification"
    ESTIME = "estime"
    A_ATTRIBUER = "a_attribuer"
    EN_RETRANSCRIPTION = "en_retranscription"
    A_CORRIGER = "a_corriger"
    EN_CORRECTION = "en_correction"
    EN_MISE_EN_FORME = "en_mise_en_forme"
    CALCUL_EN_COURS = "calcul_en_cours"
    A_VALIDER = "a_valider"
    ENVOYE = "envoye"
    FACTURE = "facture"
    PAYE_ENTRANT = "paye_entrant"
    PRESTATAIRES_PAYES = "prestataires_payes"
    ARCHIVE = "archive"
    # Cas particuliers
    BLOQUE = "bloque"
    INCOMPLET = "incomplet"


class TypeInstanceEnum(str, PyEnum):
    CE = "CE"
    CMAS = "CMAS"
    CSSCT = "CSSCT"
    AUTRE = "Autre"


class NiveauConfidentialiteEnum(str, PyEnum):
    STANDARD = "standard"
    RENFORCE = "renforce"
    ABSOLU = "absolu"


class Dossier(Base):
    __tablename__ = "dossiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    titre: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    statut: Mapped[StatutDossierEnum] = mapped_column(
        Enum(StatutDossierEnum), nullable=False, default=StatutDossierEnum.RECU
    )
    type_instance: Mapped[TypeInstanceEnum] = mapped_column(Enum(TypeInstanceEnum), nullable=False)
    date_seance: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_reception_audio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_limite: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_envoi_client: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Flags urgence / retard
    est_urgent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    urgence_forcee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Clients
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    payeur_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True
    )

    # Audio
    duree_audio_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Pages (base de calcul tarifaire)
    nombre_pages_final: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    # Tarification — JSONB critères saisis à la qualification
    criteres_tarif: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # FK vers le calcul tarifaire courant (peut évoluer à chaque recalcul)
    calcul_tarifaire_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calculs_tarifaires.id"), nullable=True
    )

    # Confidentialité
    niveau_confidentialite: Mapped[NiveauConfidentialiteEnum] = mapped_column(
        Enum(NiveauConfidentialiteEnum), default=NiveauConfidentialiteEnum.STANDARD, nullable=False
    )
    notes_internes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Snapshot immuable à l'archivage
    archive_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        onupdate=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )

    # Relations
    client = relationship("Client", foreign_keys=[client_id], back_populates="dossiers")
    payeur = relationship("Client", foreign_keys=[payeur_id])
    affectations = relationship("Affectation", back_populates="dossier", lazy="dynamic")
    journal = relationship("JournalActivite", back_populates="dossier", lazy="dynamic")
    incidents = relationship("IncidentQualite", back_populates="dossier", lazy="dynamic")
    calcul_tarifaire = relationship(
        "CalculTarifaire", foreign_keys=[calcul_tarifaire_id], post_update=True
    )
    calculs = relationship(
        "CalculTarifaire",
        primaryjoin="CalculTarifaire.dossier_id == Dossier.id",
        foreign_keys="CalculTarifaire.dossier_id",
        lazy="dynamic",
        overlaps="calcul_tarifaire",
    )
    fichiers = relationship("FichierDossier", back_populates="dossier", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Dossier {self.reference} [{self.statut.value}]>"
