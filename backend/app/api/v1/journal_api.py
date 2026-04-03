import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.journal import JournalActivite
from app.models.dossier import Dossier
from app.models.user import User
from app.schemas.journal import JournalEntryOut

router = APIRouter()


@router.get("/dossiers/{dossier_id}/journal", response_model=List[JournalEntryOut])
def get_journal_dossier(
    dossier_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    limit: int = 50,
    offset: int = 0,
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return (
        db.query(JournalActivite)
        .filter(JournalActivite.dossier_id == dossier_id)
        .order_by(JournalActivite.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/journal", response_model=List[JournalEntryOut])
def get_journal_global(
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
    limit: int = 100,
    offset: int = 0,
    type_action: Optional[str] = None,
):
    q = db.query(JournalActivite)
    if type_action:
        q = q.filter(JournalActivite.type_action == type_action)
    return q.order_by(JournalActivite.timestamp.desc()).offset(offset).limit(limit).all()
