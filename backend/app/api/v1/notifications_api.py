import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import DbDep, CurrentUser, require_permission
from app.core.config import settings
from app.models.refonte import Notification
from app.models.user import User
from app.services.alertes import executer_alertes
from app.services.notifications import marquer_lue

router = APIRouter(prefix="/notifications")


def _out(n: Notification) -> dict:
    return {"id": str(n.id), "type": n.type, "titre": n.titre, "message": n.message, "lien": n.lien,
            "dossier_id": str(n.dossier_id) if n.dossier_id else None, "lu": n.lu_le is not None,
            "email_statut": n.email_statut, "created_at": n.created_at}


@router.get("")
def mes_notifications(db: DbDep, user: CurrentUser, non_lues: bool = False,
                      limit: int = Query(default=30, ge=1, le=200)):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if non_lues:
        q = q.filter(Notification.lu_le.is_(None))
    total_non_lues = db.query(Notification).filter(Notification.user_id == user.id,
                                                   Notification.lu_le.is_(None)).count()
    return {"non_lues": total_non_lues, "email_configure": settings.brevo_configured,
            "items": [_out(n) for n in q.order_by(Notification.created_at.desc()).limit(limit).all()]}


@router.post("/{notif_id}/lu")
def lire(notif_id: uuid.UUID, db: DbDep, user: CurrentUser):
    n = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == user.id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    marquer_lue(n)
    db.commit()
    return _out(n)


@router.post("/tout-lu")
def tout_lire(db: DbDep, user: CurrentUser):
    for n in db.query(Notification).filter(Notification.user_id == user.id, Notification.lu_le.is_(None)).all():
        marquer_lue(n)
    db.commit()
    return {"ok": True}


@router.post("/alertes/executer")
def lancer_alertes(db: DbDep, _u: User = Depends(require_permission("dossiers.gerer"))):
    return executer_alertes(db)
