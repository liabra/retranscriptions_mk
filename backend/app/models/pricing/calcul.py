from typing import Optional
import uuid
from enum import Enum as PyEnum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Integer, Numeric, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base


class StatutCalculEnum(str, PyEnum):
    ESTIMATIF = "estimatif"    # Basé sur durée audio
    DEFINITIF = "definitif"    # Basé sur pages réelles
    AJUSTE = "ajuste"          # Après ajustement manuel


class CalculTarifaire(Base):
    """
    Source de vérité financière d'un dossier.
    Immuable une fois validé. Tout recalcul crée une nouvelle version.
    Le moteur distingue montant CLIENT et montant PRESTATAIRES.
    """
    __tablename__ = "calculs_tarifaires"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dossiers.id"), nullable=False, index=True
    )

    # Version : 1 = estimation, 2 = recalcul post-pages, 3+ = recalcul manuel
    version_calcul: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    date_calcul: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    declenche_par_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Base de calcul
    nombre_pages: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    # Snapshot des critères du dossier au moment du calcul
    criteres_appliques: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Liste ordonnée des règles appliquées avec leur résultat (traçabilité complète)
    # Structure : [{regle_id, regle_libelle, grille_id, grille_version, condition_evaluee,
    #               valeur_appliquee, impact_montant, cible, ordre_application}, ...]
    regles_appliquees: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # ─── Montant CLIENT ────────────────────────────────────────────────
    montant_client_brut: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    ajustement_client: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    motif_ajustement_client: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    montant_client_final: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # ─── Montant PRESTATAIRES (calculés indépendamment) ─────────────────
    montant_retranscripteur: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    montant_correcteur: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    montant_prestataires_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # ─── Marge brute ─────────────────────────────────────────────────
    marge_brute: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Snapshot des versions de grilles utilisées (pour audit futur)
    grilles_version_snap: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    statut: Mapped[StatutCalculEnum] = mapped_column(
        Enum(StatutCalculEnum), default=StatutCalculEnum.ESTIMATIF, nullable=False
    )
    valide_par_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Relations
    dossier = relationship(
        "Dossier",
        foreign_keys=[dossier_id],
        back_populates="calculs",
        overlaps="calcul_tarifaire",
    )
    declenche_par = relationship("User", foreign_keys=[declenche_par_id])
    valide_par = relationship("User", foreign_keys=[valide_par_id])

    def __repr__(self) -> str:
        return f"<CalculTarifaire dossier={self.dossier_id} v{self.version_calcul} client={self.montant_client_final}€>"
