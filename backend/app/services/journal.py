"""
Service de journalisation immuable.
Toute action sur un dossier est tracée ici.
Le journal ne peut jamais être modifié ni supprimé.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.journal import JournalActivite, TypeActionEnum


def log_action(
    db: Session,
    type_action: TypeActionEnum,
    dossier_id: Optional[uuid.UUID] = None,
    utilisateur_id: Optional[uuid.UUID] = None,
    detail: Optional[Dict[str, Any]] = None,
    ip_source: Optional[str] = None,
) -> JournalActivite:
    """Crée une entrée immuable dans le journal d'activité."""
    entry = JournalActivite(
        timestamp=datetime.now(timezone.utc),
        dossier_id=dossier_id,
        utilisateur_id=utilisateur_id,
        type_action=type_action,
        detail=detail,
        ip_source=ip_source,
    )
    db.add(entry)
    # Flush sans commit pour permettre de grouper avec d'autres opérations
    db.flush()
    return entry
