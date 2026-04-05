"""
Service OneDrive — Microsoft Graph API (client credentials flow).
Si les variables ONEDRIVE_* ne sont pas configurées, chaque fonction retourne None
et le code appelant doit gérer le fallback stockage local.
"""
import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    return bool(
        settings.ONEDRIVE_TENANT_ID
        and settings.ONEDRIVE_CLIENT_ID
        and settings.ONEDRIVE_CLIENT_SECRET
        and settings.ONEDRIVE_DRIVE_ID
    )


def _get_token() -> "str | None":
    """Obtient un access token via OAuth2 client credentials (sans dépendance externe)."""
    url = (
        f"https://login.microsoftonline.com/{settings.ONEDRIVE_TENANT_ID}"
        f"/oauth2/v2.0/token"
    )
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": settings.ONEDRIVE_CLIENT_ID,
        "client_secret": settings.ONEDRIVE_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())["access_token"]
    except Exception as exc:
        logger.warning(f"[OneDrive] Échec token: {exc}")
        return None


def upload_file(content: bytes, filename: str, folder: str) -> "Optional[str]":
    """
    Upload un fichier dans OneDrive.

    Args:
        content: bytes du fichier
        filename: nom du fichier (safe, sans slashes)
        folder: chemin relatif du dossier dans le Drive (ex: "Depot-Prestataires/dossier-123")

    Returns:
        URL publique OneDrive si succès, None si non configuré ou erreur.
    """
    if not _is_configured():
        return None

    token = _get_token()
    if not token:
        return None

    # Graph API upload: PUT /drives/{driveId}/root:/{folder}/{filename}:/content
    safe_folder = folder.strip("/")
    upload_url = (
        f"https://graph.microsoft.com/v1.0/drives/{settings.ONEDRIVE_DRIVE_ID}"
        f"/root:/{safe_folder}/{filename}:/content"
    )
    req = urllib.request.Request(upload_url, data=content, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/octet-stream")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            # webUrl = lien direct OneDrive (accessible via navigateur)
            web_url = result.get("webUrl") or result.get("@microsoft.graph.downloadUrl", "")
            logger.info(f"[OneDrive] Upload OK: {folder}/{filename}")
            return web_url
    except Exception as exc:
        logger.warning(f"[OneDrive] Échec upload '{folder}/{filename}': {exc}")
        return None
