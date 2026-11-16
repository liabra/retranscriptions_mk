"""
Détection automatique des nouveaux audios (mode B) — Microsoft Graph delta query.

- Surveille ONEDRIVE_INBOX_FOLDER ; chaque nouveau fichier audio crée une entrée
  « à traiter » dans `audios` (jamais de dossier créé automatiquement).
- Anti-doublon : unicité (drive_id, item_id) ; un fichier déjà connu n'est jamais réimporté.
- Reprise : le deltaLink est conservé en base ; en cas d'erreur, il n'est pas avancé
  (la prochaine exécution reprend au même point) et l'erreur est enregistrée.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.refonte import AudioSource, GraphSyncState
from app.services import onedrive as graph
from app.services.notifications import internes, notifier

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".mp4", ".aac", ".ogg", ".flac", ".wma", ".webm")
STATE_ID = "inbox"


def _est_audio(item: dict) -> bool:
    if "file" not in item or item.get("deleted"):
        return False
    name = (item.get("name") or "").lower()
    mime = ((item.get("file") or {}).get("mimeType") or "").lower()
    return name.endswith(AUDIO_EXTENSIONS) or mime.startswith("audio/")


def run_sync(db: Session, client: Optional[graph.GraphClient] = None) -> GraphSyncState:
    state = db.query(GraphSyncState).filter(GraphSyncState.id == STATE_ID).with_for_update().first()
    if not state:
        state = GraphSyncState(id=STATE_ID, echecs_consecutifs=0, nouveaux_detectes=0)
        db.add(state)
        db.flush()
    state.derniere_execution = datetime.now(timezone.utc)
    try:
        client = client or graph.GraphClient()
        items, new_link = client.delta(settings.ONEDRIVE_INBOX_FOLDER, state.delta_link)
    except graph.GraphError as exc:
        state.derniere_erreur = str(exc)[:500]
        state.echecs_consecutifs = (state.echecs_consecutifs or 0) + 1
        db.commit()
        logger.warning("[GRAPH SYNC] échec : %s", exc)
        return state

    nouveaux = 0
    for item in items:
        if not _est_audio(item):
            continue
        meta = graph.item_metadata(item)
        drive_id = meta["drive_id"] or settings.ONEDRIVE_DRIVE_ID
        if not meta["item_id"]:
            continue
        existing = db.query(AudioSource).filter(
            AudioSource.drive_id == drive_id, AudioSource.item_id == meta["item_id"]
        ).first()
        if existing:
            existing.etag = meta["etag"]  # synchronisation des changements (renommage, nouvelle version)
            existing.nom_fichier = meta["nom"][:500]
            existing.taille_octets = meta["taille"]
            continue
        duree = round(meta["duree_ms"] / 60000) if meta.get("duree_ms") else None
        db.add(AudioSource(
            nom_fichier=meta["nom"][:500], taille_octets=meta["taille"], mime_type=meta["mime"],
            duree_minutes=duree, origine="detection_graph", stockage="onedrive",
            drive_id=drive_id, item_id=meta["item_id"], etag=meta["etag"], statut="a_traiter",
            disponible=True, verifie_le=datetime.now(timezone.utc),
        ))
        nouveaux += 1
    db.flush()
    state.delta_link = new_link
    state.dernier_succes = datetime.now(timezone.utc)
    state.derniere_erreur = None
    state.echecs_consecutifs = 0
    state.nouveaux_detectes = nouveaux
    if nouveaux:
        notifier(db, internes(db, "audios.gerer"), "nouvel_audio",
                 f"{nouveaux} nouvel(s) audio(s) détecté(s) dans OneDrive",
                 "Qualifiez-les pour créer les missions.", lien="/audios")
    db.commit()
    return state
