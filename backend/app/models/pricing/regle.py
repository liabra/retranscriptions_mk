from typing import Optional
import uuid
from enum import Enum as PyEnum
from decimal import Decimal

from sqlalchemy import String, Boolean, Integer, Numeric, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base_class import Base


class TypeRegleEnum(str, PyEnum):
    BASE = "base"                        # Tarif de base par page
    MAJORATION = "majoration"            # Ajout au montant
    REMISE = "remise"                    # Soustraction au montant
    FORFAIT = "forfait"                  # Remplacement partiel ou total
    PLANCHER = "plancher"                # Montant minimum garanti
    PLAFOND = "plafond"                  # Montant maximum autorisé


class ConditionTypeEnum(str, PyEnum):
    TOUJOURS = "toujours"
    SI_TYPE_INSTANCE = "si_type_instance"
    SI_URGENCE = "si_urgence"
    SI_SNP = "si_snp"
    SI_SPECIAL = "si_special"
    SI_DUREE = "si_duree"
    SI_VOLUME = "si_volume"              # Basé sur le nombre de pages
    SI_CLIENT = "si_client"
    COMBINEE = "combinee"                # Plusieurs conditions


class ModeCalculEnum(str, PyEnum):
    PAR_PAGE = "par_page"
    FORFAIT_FIXE = "forfait_fixe"
    POURCENTAGE_BASE = "pourcentage_base"    # % du tarif de base
    POURCENTAGE_TOTAL = "pourcentage_total"  # % du total en cours
    MULTIPLICATEUR = "multiplicateur"


class RegleTarifaire(Base):
    """
    Brique élémentaire du moteur. Définit un tarif ou modificateur pour une condition précise.
    Toutes les valeurs métier (montants, taux) sont ici — jamais dans le code applicatif.
    """
    __tablename__ = "regles_tarifaires"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grille_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grilles_tarifaires.id", ondelete="CASCADE"), nullable=False
    )

    libelle: Mapped[str] = mapped_column(String(255), nullable=False)
    type_regle: Mapped[TypeRegleEnum] = mapped_column(Enum(TypeRegleEnum), nullable=False)

    condition_type: Mapped[ConditionTypeEnum] = mapped_column(
        Enum(ConditionTypeEnum), default=ConditionTypeEnum.TOUJOURS, nullable=False
    )
    # Ex: {"type_instance": "CSSCT"} ou {"urgence": true, "delai_h": 48}
    condition_valeur: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    mode_calcul: Mapped[ModeCalculEnum] = mapped_column(Enum(ModeCalculEnum), nullable=False)
    valeur: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    unite: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "€/page", "%", "multiplicateur"

    priorite: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    cumulable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    plafond_montant: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relations
    grille = relationship("GrilleTarifaire", back_populates="regles")

    def __repr__(self) -> str:
        return f"<RegleTarifaire {self.libelle} [{self.type_regle.value}] valeur={self.valeur}>"
