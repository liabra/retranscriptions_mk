import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import DbDep, require_permission
from app.models.journal import JournalActivite, TypeActionEnum
from app.models.dossier import Dossier
from app.models.user import User
from app.schemas.journal import JournalEntryOut

router = APIRouter()


@router.get("/dossiers/{dossier_id}/journal", response_model=List[JournalEntryOut])
def get_journal_dossier(
    dossier_id: uuid.UUID,
    db: DbDep,
    current_user: User = Depends(require_permission("journal.voir")),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
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
    admin: User = Depends(require_permission("journal.voir")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    type_action: Optional[str] = None,
):
    q = db.query(JournalActivite)
    if type_action:
        try:
            q = q.filter(JournalActivite.type_action == TypeActionEnum(type_action))
        except ValueError:
            raise HTTPException(status_code=400, detail="Type d'action inconnu")
    return q.order_by(JournalActivite.timestamp.desc()).offset(offset).limit(limit).all()
