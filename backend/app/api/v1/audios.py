"""
Audios originaux — accès réservé aux responsables internes.

Le lien OneDrive privé saisi est chiffré en base et n'est JAMAIS renvoyé, même aux
responsables (seule la plateforme s'en sert, via Microsoft Graph).
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.api.v1.common import audio_public, stream_response, get_dossier
from app.core.config import settings
from app.core.deps import DbDep, require_permission
from app.core.security import encrypt_secret
from app.models.client import Client
from app.models.journal import TypeActionEnum
from app.models.refonte import AudioSource, GraphSyncState
from app.models.user import User
from app.services import onedrive as graph
from app.services import storage
from app.services.graph_sync import run_sync, STATE_ID, AUDIO_EXTENSIONS
from app.services.journal import log_action

router = APIRouter()

_AUDIO_MIME = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".mp4": "video/mp4",
               ".aac": "audio/aac", ".ogg": "audio/ogg", ".flac": "audio/flac", ".webm": "audio/webm",
               ".wma": "audio/x-ms-wma"}


class AudioLien(BaseModel):
    url: str = Field(min_length=10, max_length=2000)
    client_id: Optional[uuid.UUID] = None
    nom: Optional[str] = Field(default=None, max_length=300)
    duree_minutes: Optional[int] = Field(default=None, ge=0, le=6000)


class Associer(BaseModel):
    dossier_id: uuid.UUID


class AudioMaj(BaseModel):
    client_id: Optional[uuid.UUID] = None
    duree_minutes: Optional[int] = Field(default=None, ge=0, le=6000)
    nom_fichier: Optional[str] = Field(default=None, max_length=300)


def _signature_audio(head: bytes, suffix: str) -> bool:
    """Vérifie le type réel (octets de signature), pas seulement l'extension."""
    if suffix == ".mp3":
        return head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0)
    if suffix == ".wav":
        return head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    if suffix in (".m4a", ".mp4"):
        return head[4:8] == b"ftyp"
    if suffix == ".ogg":
        return head.startswith(b"OggS")
    if suffix == ".flac":
        return head.startswith(b"fLaC")
    if suffix == ".webm":
        return head.startswith(b"\x1a\x45\xdf\xa3")
    if suffix == ".aac":
        return len(head) > 1 and head[0] == 0xFF and (head[1] & 0xF6) == 0xF0
    return False


def _get_audio(db, audio_id: uuid.UUID) -> AudioSource:
    a = db.query(AudioSource).filter(AudioSource.id == audio_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Audio introuvable")
    return a


def _out(db, a: AudioSource) -> dict:
    out = audio_public(a)
    client = db.query(Client).filter(Client.id == a.client_id).first() if a.client_id else None
    out["client_nom"] = client.nom if client else None
    return out


def _appliquer_verification(a: AudioSource, item: dict) -> None:
    meta = graph.item_metadata(item)
    if "file" not in item:
        raise HTTPException(status_code=400, detail="Le lien pointe vers un dossier, pas vers un fichier audio")
    nom = (meta["nom"] or "").lower()
    if not (nom.endswith(AUDIO_EXTENSIONS) or (meta["mime"] or "").startswith("audio/")):
        raise HTTPException(status_code=400, detail="Le fichier lié n'est pas un fichier audio")
    a.drive_id, a.item_id, a.etag = meta["drive_id"], meta["item_id"], meta["etag"]
    a.nom_fichier = (meta["nom"] or a.nom_fichier)[:500]
    a.taille_octets, a.mime_type = meta["taille"], meta["mime"]
    if meta.get("duree_ms") and not a.duree_minutes:
        a.duree_minutes = round(meta["duree_ms"] / 60000)
    a.disponible = True
    a.verifie_le = datetime.now(timezone.utc)
    a.message_verification = "Fichier accessible sur OneDrive"


@router.get("/audios")
def list_audios(db: DbDep, _u: User = Depends(require_permission("audios.gerer")),
                statut: Optional[str] = Query(default="a_traiter"),
                limit: int = Query(default=100, ge=1, le=500)):
    q = db.query(AudioSource)
    if statut in ("a_traiter", "associe", "ignore"):
        q = q.filter(AudioSource.statut == statut)
    return [_out(db, a) for a in q.order_by(AudioSource.created_at.desc()).limit(limit).all()]


@router.post("/audios/lien", status_code=201)
def ajouter_lien(payload: AudioLien, db: DbDep, user: User = Depends(require_permission("audios.gerer"))):
    url = payload.url.strip()
    if not graph.lien_onedrive_valide(url):  # fix: anti-SSRF, domaines Microsoft uniquement
        raise HTTPException(status_code=400, detail="Lien non reconnu : utilisez un lien OneDrive ou SharePoint (https)")
    if payload.client_id and not db.query(Client).filter(Client.id == payload.client_id).first():
        raise HTTPException(status_code=400, detail="Client introuvable")
    a = AudioSource(
        nom_fichier=(payload.nom or "Audio (lien OneDrive)")[:500], duree_minutes=payload.duree_minutes,
        origine="lien_manuel", stockage="onedrive", lien_prive_chiffre=encrypt_secret(url),
        client_id=payload.client_id, statut="a_traiter", disponible=False, ajoute_par_id=user.id,
    )
    if graph.is_configured():
        try:
            _appliquer_verification(a, graph.GraphClient().resolve_share_link(url))
        except graph.GraphError as exc:
            raise HTTPException(status_code=400, detail=f"Lien inaccessible : {exc}")
        doublon = db.query(AudioSource).filter(AudioSource.drive_id == a.drive_id,
                                               AudioSource.item_id == a.item_id).first()
        if doublon:
            raise HTTPException(status_code=409, detail="Cet audio est déjà enregistré dans la plateforme")
    else:
        a.message_verification = ("Vérification impossible : OneDrive n'est pas encore configuré. "
                                  "Le téléchargement par le retranscripteur sera disponible après vérification.")
    db.add(a)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cet audio est déjà enregistré dans la plateforme")
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, utilisateur_id=user.id,
               detail={"action": "ajout_audio_lien", "audio_id": str(a.id), "verifie": a.disponible})
    db.commit()
    return _out(db, a)


async def enregistrer_fichier_audio(db, user: User, file: UploadFile, client_id: Optional[uuid.UUID],
                                    duree_minutes: Optional[int], origine: str) -> AudioSource:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _AUDIO_MIME:
        raise HTTPException(status_code=400, detail=f"Format audio non accepté ({', '.join(sorted(_AUDIO_MIME))})")
    max_bytes = settings.MAX_AUDIO_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (maximum {settings.MAX_AUDIO_MB} Mo)")
    if not _signature_audio(content[:16], suffix):
        raise HTTPException(status_code=400, detail="Le contenu du fichier ne correspond pas à un audio valide")
    client = db.query(Client).filter(Client.id == client_id).first() if client_id else None
    if client_id and not client:
        raise HTTPException(status_code=400, detail="Client introuvable")
    folder = "/".join([settings.ONEDRIVE_ROOT_FOLDER.strip("/"),
                       graph.nettoyer_nom(client.nom if client else "Non classés"), "Audios"])
    stored = storage.save_audio(content, folder, file.filename or f"audio{suffix}")
    a = AudioSource(
        nom_fichier=(file.filename or f"audio{suffix}")[:500], taille_octets=len(content),
        mime_type=_AUDIO_MIME[suffix], duree_minutes=duree_minutes, origine=origine,
        client_id=client_id, statut="a_traiter", disponible=True, ajoute_par_id=user.id,
        verifie_le=datetime.now(timezone.utc), message_verification="Fichier enregistré", **stored,
    )
    db.add(a)
    db.flush()
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, utilisateur_id=user.id,
               detail={"action": "ajout_audio_fichier", "audio_id": str(a.id), "taille": len(content),
                       "stockage": a.stockage, "origine": origine})
    return a


@router.post("/audios/fichier", status_code=201)
async def ajouter_fichier(
    db: DbDep, user: User = Depends(require_permission("audios.gerer")),
    file: UploadFile = File(...), client_id: Optional[uuid.UUID] = Form(default=None),
    duree_minutes: Optional[int] = Form(default=None),
):
    a = await enregistrer_fichier_audio(db, user, file, client_id, duree_minutes, "fichier")
    db.commit()
    return _out(db, a)


@router.patch("/audios/{audio_id}")
def modifier(audio_id: uuid.UUID, payload: AudioMaj, db: DbDep,
             _u: User = Depends(require_permission("audios.gerer"))):
    a = _get_audio(db, audio_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("client_id") and not db.query(Client).filter(Client.id == changes["client_id"]).first():
        raise HTTPException(status_code=400, detail="Client introuvable")
    for k, v in changes.items():
        setattr(a, k, v)
    db.commit()
    return _out(db, a)


@router.post("/audios/{audio_id}/verifier")
def verifier(audio_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("audios.gerer"))):
    a = _get_audio(db, audio_id)
    if a.stockage == "local":
        return _out(db, a)
    try:
        client = graph.GraphClient()
        if a.drive_id and a.item_id:
            _appliquer_verification(a, client.get_item(a.drive_id, a.item_id))
        elif a.lien_prive_chiffre:
            from app.core.security import decrypt_secret
            url = decrypt_secret(a.lien_prive_chiffre)
            if not url:
                raise HTTPException(status_code=500, detail="Lien illisible (clé de chiffrement modifiée ?)")
            _appliquer_verification(a, client.resolve_share_link(url))
    except graph.GraphNotConfigured:
        raise HTTPException(status_code=503, detail="OneDrive n'est pas configuré")
    except graph.GraphError as exc:
        a.disponible = False
        a.verifie_le = datetime.now(timezone.utc)
        a.message_verification = f"Inaccessible : {exc}"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ce fichier OneDrive est déjà enregistré sous un autre audio")
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, utilisateur_id=user.id,
               detail={"action": "verification_audio", "audio_id": str(a.id), "disponible": a.disponible})
    db.commit()
    return _out(db, a)


@router.post("/audios/{audio_id}/associer")
def associer(audio_id: uuid.UUID, payload: Associer, db: DbDep,
             user: User = Depends(require_permission("audios.gerer"))):
    a = _get_audio(db, audio_id)
    d = get_dossier(db, payload.dossier_id)
    if d.statut_production not in ("a_qualifier", "a_attribuer", "attribue"):
        raise HTTPException(status_code=409, detail="L'audio ne peut plus être changé à ce stade")
    for ancien in db.query(AudioSource).filter(AudioSource.dossier_id == d.id, AudioSource.id != a.id).all():
        ancien.dossier_id = None
        ancien.statut = "a_traiter"
    a.dossier_id = d.id
    a.client_id = a.client_id or d.client_id
    a.statut = "associe"
    if a.duree_minutes and not d.duree_audio_minutes:
        d.duree_audio_minutes = a.duree_minutes
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "association_audio", "audio_id": str(a.id)})
    db.commit()
    return _out(db, a)


@router.post("/audios/{audio_id}/ignorer")
def ignorer(audio_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("audios.gerer"))):
    a = _get_audio(db, audio_id)
    if a.dossier_id:
        raise HTTPException(status_code=409, detail="Audio déjà associé à un dossier")
    a.statut = "ignore"
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, utilisateur_id=user.id,
               detail={"action": "audio_ignore", "audio_id": str(a.id)})
    db.commit()
    return _out(db, a)


@router.post("/audios/{audio_id}/retablir")
def retablir(audio_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("audios.gerer"))):
    a = _get_audio(db, audio_id)
    if a.statut == "ignore":
        a.statut = "a_traiter"
        db.commit()
    return _out(db, a)


@router.get("/audios/{audio_id}/fichier")
def telecharger(audio_id: uuid.UUID, db: DbDep,
                user: User = Depends(require_permission("audios.gerer", "relecture"))):
    a = _get_audio(db, audio_id)
    chunks = storage.stream_audio(a)
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, dossier_id=a.dossier_id, utilisateur_id=user.id,
               detail={"action": "telechargement_audio", "audio_id": str(a.id)})
    db.commit()
    return stream_response(chunks, a.nom_fichier, a.mime_type or "application/octet-stream", a.taille_octets)


@router.get("/audios-synchronisation")
def etat_synchro(db: DbDep, _u: User = Depends(require_permission("audios.gerer"))):
    s = db.query(GraphSyncState).filter(GraphSyncState.id == STATE_ID).first()
    return {
        "onedrive_configure": graph.is_configured(),
        "detection_automatique_active": graph.is_configured() and settings.GRAPH_SYNC_INTERVAL_MINUTES > 0,
        "intervalle_minutes": settings.GRAPH_SYNC_INTERVAL_MINUTES,
        "dossier_surveille": settings.ONEDRIVE_INBOX_FOLDER,
        "derniere_execution": s.derniere_execution if s else None,
        "dernier_succes": s.dernier_succes if s else None,
        "derniere_erreur": s.derniere_erreur if s else None,
        "echecs_consecutifs": s.echecs_consecutifs if s else 0,
        "nouveaux_detectes": s.nouveaux_detectes if s else 0,
    }


@router.post("/audios-synchronisation")
def lancer_synchro(db: DbDep, _u: User = Depends(require_permission("audios.gerer"))):
    if not graph.is_configured():
        raise HTTPException(status_code=503, detail="OneDrive n'est pas configuré")
    run_sync(db)
    return etat_synchro(db, _u)
