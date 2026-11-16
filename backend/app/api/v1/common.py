"""Aides partagées par les routes : chargement contrôlé, sérialisation par profil."""
import uuid
from datetime import date, datetime, timezone
from typing import Iterable, Iterator, List, Optional
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session

from app.models.affectation import Affectation, StatutAffectationEnum
from app.models.client import Client
from app.models.dossier import Dossier
from app.models.prestataire import Prestataire
from app.models.refonte import AudioSource, Livraison, DemandeCorrection
from app.models.user import User
from app.services.workflow import PRODUCTION_LABELS, FACTURATION_LABELS

AFF_ACTIVES = (StatutAffectationEnum.EN_ATTENTE, StatutAffectationEnum.EN_COURS, StatutAffectationEnum.LIVRE)


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_dossier(db: Session, dossier_id: uuid.UUID, lock: bool = False) -> Dossier:
    q = db.query(Dossier).filter(Dossier.id == dossier_id, Dossier.supprime_le.is_(None))
    if lock:
        q = q.with_for_update()
    d = q.first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return d


def affectation_active(db: Session, dossier_id: uuid.UUID) -> Optional[Affectation]:
    return db.query(Affectation).filter(
        Affectation.dossier_id == dossier_id,
        Affectation.statut.in_(AFF_ACTIVES + (StatutAffectationEnum.VALIDE,)),
    ).order_by(Affectation.date_attribution.desc()).first()


def audio_du_dossier(db: Session, dossier_id: uuid.UUID) -> Optional[AudioSource]:
    return db.query(AudioSource).filter(AudioSource.dossier_id == dossier_id).order_by(
        AudioSource.created_at.desc()).first()


def en_retard(d: Dossier, aff: Optional[Affectation]) -> bool:
    if d.statut_production in ("valide", "archive", "bloque"):
        return False
    today = date.today()
    if d.date_limite and d.date_limite < today:
        return True
    if aff and aff.date_limite_rendu and d.statut_production in ("attribue", "en_cours", "correction_demandee"):
        lim = aff.date_limite_rendu if aff.date_limite_rendu.tzinfo else aff.date_limite_rendu.replace(tzinfo=timezone.utc)
        return lim < now()
    return False


def audio_public(a: Optional[AudioSource]) -> Optional[dict]:
    """Vue d'un audio SANS aucune information de localisation (ni lien, ni identifiant Graph)."""
    if not a:
        return None
    return {
        "id": str(a.id), "nom_fichier": a.nom_fichier, "taille_octets": a.taille_octets,
        "mime_type": a.mime_type, "duree_minutes": a.duree_minutes, "origine": a.origine,
        "disponible": a.disponible, "statut": a.statut, "message_verification": a.message_verification,
        "verifie_le": a.verifie_le, "created_at": a.created_at,
        "client_id": str(a.client_id) if a.client_id else None,
        "dossier_id": str(a.dossier_id) if a.dossier_id else None,
    }


def livraison_out(l: Livraison, detail: bool = True) -> dict:
    out = {
        "id": str(l.id), "dossier_id": str(l.dossier_id), "version": l.version, "type_depot": l.type_depot,
        "nom_original": l.nom_original, "taille_octets": l.taille_octets, "statut_controle": l.statut_controle,
        "pages_declarees": l.pages_declarees, "commentaire": l.commentaire,
        "depose_par": l.depose_par.nom if l.depose_par else None, "depose_le": l.depose_le,
    }
    if detail:
        out["rapport_controle"] = l.rapport_controle
    return out


def correction_out(c: DemandeCorrection) -> dict:
    return {
        "id": str(c.id), "message": c.message, "created_at": c.created_at, "date_limite": c.date_limite,
        "livraison_id": str(c.livraison_id) if c.livraison_id else None,
        "demandee_par": c.demandee_par.nom if c.demandee_par else None,
        "resolue_le": c.resolue_le,
    }


def dossier_resume(db: Session, d: Dossier) -> dict:
    """Vue interne d'un dossier pour les listes."""
    aff = affectation_active(db, d.id)
    presta = db.query(Prestataire).filter(Prestataire.id == aff.prestataire_id).first() if aff else None
    client = db.query(Client).filter(Client.id == d.client_id).first()
    return {
        "id": str(d.id), "reference": d.reference, "titre": d.titre,
        "type_instance": d.type_instance.value, "client_id": str(d.client_id),
        "client_nom": client.nom if client else None,
        "statut_production": d.statut_production,
        "statut_production_label": PRODUCTION_LABELS.get(d.statut_production, d.statut_production),
        "statut_facturation": d.statut_facturation,
        "statut_facturation_label": FACTURATION_LABELS.get(d.statut_facturation, d.statut_facturation),
        "date_seance": d.date_seance, "date_limite": d.date_limite,
        "date_limite_rendu": aff.date_limite_rendu if aff else None,
        "est_urgent": d.est_urgent, "en_retard": en_retard(d, aff),
        "duree_audio_minutes": d.duree_audio_minutes,
        "retranscripteur": {"id": str(presta.id), "nom": presta.nom} if presta else None,
        "created_at": d.created_at, "updated_at": d.updated_at,
    }


def content_disposition(filename: str) -> str:
    safe = "".join(c for c in filename if c.isprintable() and c not in '"\\\r\n') or "fichier"
    ascii_name = safe.encode("ascii", "ignore").decode() or "fichier"
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(safe)}'


def stream_response(chunks: Iterator[bytes], filename: str, media_type: str,
                    size: Optional[int] = None) -> StreamingResponse:
    headers = {"Content-Disposition": content_disposition(filename),
               "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if size:
        headers["Content-Length"] = str(size)
    return StreamingResponse(chunks, media_type=media_type, headers=headers)


def bytes_response(content: bytes, filename: str, media_type: str) -> Response:
    return Response(content=content, media_type=media_type, headers={
        "Content-Disposition": content_disposition(filename),
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def users_by_ids(db: Session, ids: Iterable) -> List[User]:
    ids = [i for i in ids if i]
    return db.query(User).filter(User.id.in_(ids)).all() if ids else []
