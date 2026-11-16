"""
Notifications internes + emails.

La notification interne est toujours créée (même si l'email échoue ou n'est pas configuré).
Les emails partent après le commit de la transaction, dans un fil séparé, et leur statut
réel est enregistré (envoye / echec / non_configure).
Dédoublonnage : (user_id, dedup_key) unique.
"""
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import has_permission
from app.models.refonte import Notification
from app.models.user import User, RoleEnum
from app.services import email as email_svc

logger = logging.getLogger(__name__)

_PENDING_KEY = "notifications_email_a_envoyer"


def internes(db: Session, permission: Optional[str] = None) -> List[User]:
    """Responsables internes actives (filtrées par permission si fournie)."""
    users = db.query(User).filter(
        User.actif == True,  # noqa: E712
        User.role.in_([RoleEnum.ADMINISTRATRICE, RoleEnum.COORDINATRICE, RoleEnum.COMPTABILITE]),
    ).all()
    if permission:
        users = [u for u in users if has_permission(u, permission)]
    return users


def compte_prestataire(db: Session, prestataire_id) -> List[User]:
    if not prestataire_id:
        return []
    return db.query(User).filter(User.prestataire_id == prestataire_id, User.actif == True).all()  # noqa: E712


def notifier(
    db: Session, destinataires: Iterable[User], type_: str, titre: str,
    message: Optional[str] = None, lien: Optional[str] = None,
    dossier_id: Optional[uuid.UUID] = None, dedup_key: Optional[str] = None,
    email: bool = True, exclure: Optional[uuid.UUID] = None,
) -> List[Notification]:
    created = []
    vus = set()
    for user in destinataires:
        if user.id in vus or (exclure and user.id == exclure):
            continue
        vus.add(user.id)
        if dedup_key and db.query(Notification.id).filter(
            Notification.user_id == user.id, Notification.dedup_key == dedup_key
        ).first():
            continue
        veut_email = email and user.notif_email
        n = Notification(
            user_id=user.id, type=type_, titre=titre[:300], message=message, lien=lien,
            dossier_id=dossier_id, dedup_key=dedup_key,
            email_statut=("en_attente" if settings.brevo_configured else "non_configure") if veut_email
            else "non_demande",
        )
        db.add(n)
        db.flush()
        created.append(n)
        if veut_email and settings.brevo_configured:
            db.info.setdefault(_PENDING_KEY, []).append((n.id, user.email, user.nom, titre, message, lien))
    return created


def _send_batch(batch):
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        for notif_id, to, nom, titre, message, lien in batch:
            statut = email_svc.send(to, nom, f"[A2C] {titre}", email_svc.render(titre, message, lien))
            n = db.query(Notification).filter(Notification.id == notif_id).first()
            if n:
                n.email_statut = statut
        db.commit()
    except Exception:  # pragma: no cover — ne jamais faire échouer le fil
        logger.exception("[NOTIF] Échec de mise à jour du statut email")
        db.rollback()
    finally:
        db.close()


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session):
    batch = session.info.pop(_PENDING_KEY, None)
    if batch:
        threading.Thread(target=_send_batch, args=(batch,), daemon=True).start()


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session):
    session.info.pop(_PENDING_KEY, None)


def marquer_lue(n: Notification) -> None:
    if not n.lu_le:
        n.lu_le = datetime.now(timezone.utc)
