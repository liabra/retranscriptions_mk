"""
Services métier pour les dossiers.
- Génération de référence automatique
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.dossier import Dossier, TypeInstanceEnum


def generate_reference(db: Session, type_instance: TypeInstanceEnum) -> str:
    """
    Génère une référence unique du type : 2024-CE-0087
    Format : ANNÉE-TYPE-NUMÉRO (4 chiffres)
    """
    year = datetime.now(timezone.utc).year
    prefix = f"{year}-{type_instance.value}"

    # fix B13 : plus grand numéro existant + 1 (pas de réutilisation après suppression logique)
    import re
    refs = [r for (r,) in db.query(Dossier.reference).filter(Dossier.reference.like(f"{prefix}-%")).all()]
    nums = [int(m.group(1)) for r in refs if (m := re.match(rf"{re.escape(prefix)}-(\d+)$", r))]
    return f"{prefix}-{str(max(nums, default=0) + 1).zfill(4)}"
