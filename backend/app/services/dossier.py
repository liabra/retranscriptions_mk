"""
Services métier pour les dossiers.
- Génération de référence automatique
- Détection d'urgence
"""
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.dossier import Dossier, TypeInstanceEnum


def generate_reference(db: Session, type_instance: TypeInstanceEnum) -> str:
    """
    Génère une référence unique du type : 2024-CE-0087
    Format : ANNÉE-TYPE-NUMÉRO (4 chiffres)
    """
    year = datetime.now(timezone.utc).year
    prefix = f"{year}-{type_instance.value}"

    # Compte les dossiers de ce type pour cette année
    count = db.query(Dossier).filter(
        Dossier.reference.like(f"{prefix}-%")
    ).count()

    return f"{prefix}-{str(count + 1).zfill(4)}"


def check_urgence(date_limite: Optional[date]) -> bool:
    """
    Règle métier : tout dossier dont date_limite - now() < 48h est automatiquement URGENT.
    """
    if not date_limite:
        return False
    now = datetime.now(timezone.utc).date()
    delta = (date_limite - now).days
    return delta < 2
