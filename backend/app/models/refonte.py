"""
Modèles ajoutés par la refonte (migration 0005) :
audios sources, livraisons de PV versionnées, demandes de correction,
stockage durable des fichiers, encaissements, notifications, état de synchro Graph.

Les statuts sont stockés en texte (pas d'enum PostgreSQL natif) pour rester
compatibles avec le schéma existant, quel que soit son mode de création.
"""
from typing import Optional
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal

from sqlalchemy import (
    String, Text, Integer, BigInteger, Boolean, Numeric, Date, DateTime, ForeignKey,
    LargeBinary, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StoredBlob(Base):
    """Stockage durable en base (PostgreSQL) des PV déposés. Jamais exposé par URL."""
    __tablename__ = "stockage_fichiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contenu: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    taille_octets: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AudioSource(Base):
    """
    Audio original. Il reste dans OneDrive ; la base ne conserve que l'identifiant
    Graph (drive_id, item_id) et, pour un ajout par lien, le lien CHIFFRÉ.
    Aucun de ces éléments n'est jamais renvoyé par l'API.
    """
    __tablename__ = "audios"
    __table_args__ = (UniqueConstraint("drive_id", "item_id", name="uq_audios_drive_item"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dossier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=True, index=True
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True
    )
    nom_fichier: Mapped[str] = mapped_column(String(500), nullable=False)
    taille_octets: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duree_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # origine : lien_manuel | fichier | detection_graph | depot_client
    origine: Mapped[str] = mapped_column(String(30), nullable=False)
    # stockage : onedrive | local
    stockage: Mapped[str] = mapped_column(String(20), nullable=False, default="onedrive")
    drive_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    item_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    chemin_local: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lien_prive_chiffre: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    etag: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # statut : a_traiter | associe | ignore
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="a_traiter", index=True)
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verifie_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    message_verification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ajoute_par_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    dossier = relationship("Dossier", back_populates="audios")
    client = relationship("Client")
    ajoute_par = relationship("User")


class Livraison(Base):
    """Version d'un PV déposée (DOCX). Chaque dépôt crée une nouvelle version, jamais écrasée."""
    __tablename__ = "livraisons"
    __table_args__ = (UniqueConstraint("dossier_id", "version", name="uq_livraisons_dossier_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=False, index=True
    )
    affectation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("affectations.id"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # type : depot_prestataire | correction_interne
    type_depot: Mapped[str] = mapped_column(String(30), nullable=False, default="depot_prestataire")

    nom_original: Mapped[str] = mapped_column(String(500), nullable=False)
    taille_octets: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stockage: Mapped[str] = mapped_column(String(20), nullable=False)       # database | onedrive
    stockage_ref: Mapped[str] = mapped_column(String(300), nullable=False)  # blob id | item id
    drive_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Contrôle de conformité : conforme | avertissements | non_conforme
    statut_controle: Mapped[str] = mapped_column(String(20), nullable=False)
    rapport_controle: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pages_declarees: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    commentaire: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    depose_par_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    depose_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    dossier = relationship("Dossier", back_populates="livraisons")
    affectation = relationship("Affectation")
    depose_par = relationship("User")


class DemandeCorrection(Base):
    __tablename__ = "demandes_correction"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=False, index=True
    )
    affectation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("affectations.id"), nullable=True
    )
    livraison_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("livraisons.id"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    date_limite: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    demandee_par_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolue_par_livraison_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("livraisons.id"), nullable=True
    )
    resolue_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    demandee_par = relationship("User")


class Encaissement(Base):
    """Règlement client reçu. Immuable : une erreur se corrige par une écriture inverse motivée."""
    __tablename__ = "encaissements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factures_clients.id"), nullable=False, index=True
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    date_encaissement: Mapped[date] = mapped_column(Date, nullable=False)
    mode: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    commentaire: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    saisi_par_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    facture = relationship("FactureClient", back_populates="encaissements")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedup_key", name="uq_notifications_dedup"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    titre: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lien: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)  # chemin interne de l'app
    dossier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=True
    )
    dedup_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # email : non_demande | non_configure | en_attente | envoye | echec
    email_statut: Mapped[str] = mapped_column(String(20), nullable=False, default="non_demande")
    lu_le: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class GraphSyncState(Base):
    """État de la détection automatique (Microsoft Graph delta)."""
    __tablename__ = "graph_sync_state"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # ex. "inbox"
    delta_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    derniere_execution: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dernier_succes: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    derniere_erreur: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    echecs_consecutifs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nouveaux_detectes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RegleDelai(Base):
    """
    Délai de réalisation du PV final, compté à partir de la réception de l'audio.
    Règles évaluées par priorité croissante ; la première dont toutes les conditions
    renseignées sont remplies s'applique (une règle sans condition sert de règle par défaut).
    """
    __tablename__ = "regles_delai"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    libelle: Mapped[str] = mapped_column(String(200), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priorite: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    # Conditions (null = indifférent)
    type_instance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    duree_min_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)   # strictement supérieure à
    duree_max_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)   # inférieure ou égale à
    urgence: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    prestation: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)      # snp | special
    # Délai
    delai_jours: Mapped[int] = mapped_column(Integer, nullable=False)
    type_jours: Mapped[str] = mapped_column(String(20), nullable=False, default="calendaires")  # calendaires | ouvres
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modifie_par_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Parametre(Base):
    """Paramètres métier généraux (clé → valeur JSON), administrables sans modification du code."""
    __tablename__ = "parametres"

    cle: Mapped[str] = mapped_column(String(80), primary_key=True)
    valeur: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    modifie_par_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
