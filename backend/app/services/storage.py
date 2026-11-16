"""
Stockage des fichiers.

- PV (DOCX) : "database" (PostgreSQL, durable, sauvegardé avec la base) ou "onedrive"
  (A2C Retranscriptions/<Client>/<Dossier>/PV_vN.docx).
- Audios téléversés : "onedrive" ; "local" n'est autorisé qu'en développement/test.

Aucune bascule silencieuse : si le stockage configuré échoue, l'opération échoue (fix S8).
"""
import hashlib
import os
import uuid
from pathlib import Path
from typing import Iterator, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.refonte import StoredBlob
from app.services import onedrive as graph


class StorageError(HTTPException):
    def __init__(self, detail: str, status_code: int = 503):
        super().__init__(status_code=status_code, detail=detail)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def dossier_folder(client_nom: Optional[str], reference: str) -> str:
    return "/".join([
        settings.ONEDRIVE_ROOT_FOLDER.strip("/"),
        graph.nettoyer_nom(client_nom or "Sans client"),
        graph.nettoyer_nom(reference),
    ])


def _graph() -> graph.GraphClient:
    try:
        return graph.GraphClient()
    except graph.GraphNotConfigured:
        raise StorageError("OneDrive n'est pas configuré sur la plateforme. Contactez l'administratrice.")


# ── PV ────────────────────────────────────────────────────────────────────────

def save_pv(db: Session, content: bytes, folder: str, filename: str) -> Tuple[str, str, Optional[str]]:
    """Retourne (stockage, ref, drive_id)."""
    if settings.PV_STORAGE_BACKEND == "onedrive":
        try:
            item = _graph().upload(f"{folder}/{graph.nettoyer_nom(filename, 150)}", content)
        except graph.GraphError as exc:
            raise StorageError(f"Dépôt impossible sur OneDrive : {exc}")
        meta = graph.item_metadata(item)
        return "onedrive", meta["item_id"], meta["drive_id"] or settings.ONEDRIVE_DRIVE_ID
    blob = StoredBlob(contenu=content, taille_octets=len(content), sha256=sha256(content))
    db.add(blob)
    db.flush()
    return "database", str(blob.id), None


def load_pv(db: Session, stockage: str, ref: str, drive_id: Optional[str]) -> bytes:
    if stockage == "database":
        blob = db.query(StoredBlob).filter(StoredBlob.id == uuid.UUID(ref)).first()
        if not blob:
            raise StorageError("Fichier introuvable dans le stockage", 404)
        return blob.contenu
    if stockage == "onedrive":
        try:
            return _graph().download_bytes(drive_id or settings.ONEDRIVE_DRIVE_ID, ref)
        except graph.GraphError as exc:
            raise StorageError(f"Récupération impossible depuis OneDrive : {exc}")
    raise StorageError("Stockage inconnu", 500)


# ── Audios ────────────────────────────────────────────────────────────────────

def _local_root() -> Path:
    if settings.is_production:
        raise StorageError("Stockage local interdit en production", 500)
    root = Path(settings.LOCAL_STORAGE_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_audio(content: bytes, folder: str, filename: str) -> dict:
    """Retourne les champs de stockage d'un AudioSource."""
    if settings.AUDIO_STORAGE_BACKEND == "local":
        root = _local_root()
        name = f"{uuid.uuid4()}{Path(filename).suffix.lower()}"  # fix: nom disque opaque
        (root / name).write_bytes(content)
        return {"stockage": "local", "chemin_local": name, "drive_id": None, "item_id": None}
    try:
        item = _graph().upload(f"{folder}/{graph.nettoyer_nom(filename, 150)}", content)
    except graph.GraphError as exc:
        raise StorageError(f"Envoi impossible vers OneDrive : {exc}")
    meta = graph.item_metadata(item)
    return {"stockage": "onedrive", "chemin_local": None,
            "drive_id": meta["drive_id"] or settings.ONEDRIVE_DRIVE_ID, "item_id": meta["item_id"],
            "etag": meta["etag"]}


def stream_audio(audio) -> Iterator[bytes]:
    if audio.stockage == "local":
        root = _local_root()
        path = (root / (audio.chemin_local or "")).resolve()
        if root not in path.parents or not path.is_file():  # fix: anti path traversal
            raise StorageError("Fichier audio introuvable", 404)

        def _iter():
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(1024 * 256)
                    if not chunk:
                        break
                    yield chunk
        return _iter()
    if not audio.drive_id or not audio.item_id:
        raise StorageError("L'audio n'a pas encore été vérifié sur OneDrive : téléchargement indisponible", 409)
    client = _graph()
    gen = client.download_stream(audio.drive_id, audio.item_id)
    try:
        first = next(gen)  # déclenche les erreurs avant l'envoi des en-têtes HTTP
    except StopIteration:
        return iter(())
    except graph.GraphError as exc:
        raise StorageError(f"Audio indisponible sur OneDrive : {exc}")

    def _chain():
        yield first
        yield from gen
    return _chain()


def remove_local_file_if_any(name: Optional[str]) -> None:
    if not name or settings.is_production:
        return
    root = _local_root()
    path = (root / name).resolve()
    if root in path.parents and path.is_file():
        os.remove(path)
