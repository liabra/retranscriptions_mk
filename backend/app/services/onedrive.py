"""
Client Microsoft Graph (OneDrive) — flux « client credentials ».

Règles de sécurité :
- le jeton, les identifiants et les URL de téléchargement Graph ne quittent jamais le backend ;
- les fichiers sont servis aux utilisateurs uniquement en flux par l'API (proxy) ;
- aucune bascule silencieuse : toute erreur lève GraphError.

Tant que les variables ONEDRIVE_* ne sont pas renseignées, `is_configured()` renvoie False
et les fonctionnalités qui en dépendent répondent explicitement « OneDrive non configuré ».
"""
import base64
import logging
import re
import threading
import time
from typing import Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote, urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
_SIMPLE_UPLOAD_MAX = 4 * 1024 * 1024
_CHUNK = 320 * 1024 * 16  # 5 Mio, multiple de 320 Kio (exigence Graph)

# Hôtes acceptés pour un lien OneDrive/SharePoint saisi manuellement (anti-SSRF)
_ALLOWED_HOST_SUFFIXES = (".sharepoint.com", ".sharepoint.de", "onedrive.live.com", "1drv.ms")


class GraphError(Exception):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class GraphNotConfigured(GraphError):
    pass


def is_configured() -> bool:
    return settings.onedrive_configured


def lien_onedrive_valide(url: str) -> bool:
    try:
        p = urlparse(url)
    except ValueError:
        return False
    host = (p.hostname or "").lower()
    if p.scheme != "https" or not host:
        return False
    return any(host == s.lstrip(".") or host.endswith(s) for s in _ALLOWED_HOST_SUFFIXES)


def nettoyer_nom(nom: str, max_len: int = 80) -> str:
    """Nom de dossier/fichier sûr pour OneDrive (pas de séparateur ni caractère réservé)."""
    nom = re.sub(r'[\\/:*?"<>|#%\x00-\x1f]', "_", nom or "").strip(" .")
    return (nom or "sans_nom")[:max_len]


class _TokenCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._exp: float = 0

    def get(self, client: httpx.Client) -> str:
        with self._lock:
            if self._token and time.time() < self._exp - 120:
                return self._token
            url = f"https://login.microsoftonline.com/{settings.ONEDRIVE_TENANT_ID}/oauth2/v2.0/token"
            try:
                resp = client.post(url, data={
                    "grant_type": "client_credentials",
                    "client_id": settings.ONEDRIVE_CLIENT_ID,
                    "client_secret": settings.ONEDRIVE_CLIENT_SECRET,
                    "scope": "https://graph.microsoft.com/.default",
                }, timeout=20)
            except httpx.HTTPError as exc:
                raise GraphError(f"Connexion Microsoft impossible ({type(exc).__name__})")
            if resp.status_code != 200:
                # fix: ne jamais journaliser le corps (peut contenir des détails d'identifiants)
                raise GraphError("Authentification Microsoft refusée", resp.status_code)
            data = resp.json()
            self._token = data["access_token"]
            self._exp = time.time() + int(data.get("expires_in", 3600))
            return self._token

    def reset(self):
        with self._lock:
            self._token = None


_tokens = _TokenCache()


class GraphClient:
    def __init__(self, http: Optional[httpx.Client] = None):
        if not is_configured():
            raise GraphNotConfigured("OneDrive (Microsoft Graph) n'est pas configuré")
        self.http = http or httpx.Client(timeout=httpx.Timeout(60, connect=15), follow_redirects=False)

    # ── requêtes avec reprise ──────────────────────────────────────────────
    def _request(self, method: str, url: str, retries: int = 3, **kw) -> httpx.Response:
        base_headers = dict(kw.pop("headers", {}) or {})
        for attempt in range(retries + 1):
            headers = dict(base_headers)
            headers["Authorization"] = f"Bearer {_tokens.get(self.http)}"
            try:
                resp = self.http.request(method, url, headers=headers, **kw)
            except httpx.HTTPError as exc:
                if attempt >= retries:
                    raise GraphError(f"Microsoft Graph injoignable ({type(exc).__name__})")
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 401 and attempt < retries:
                _tokens.reset()
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = resp.headers.get("Retry-After")
                time.sleep(min(int(wait) if wait and wait.isdigit() else 2 ** attempt, 30))
                continue
            return resp
        raise GraphError("Microsoft Graph indisponible")

    @staticmethod
    def _check(resp: httpx.Response, what: str) -> dict:
        if resp.status_code >= 400:
            if resp.status_code == 404:
                raise GraphError(f"{what} : fichier introuvable ou inaccessible", 404)
            if resp.status_code == 403:
                raise GraphError(f"{what} : accès refusé par Microsoft", 403)
            raise GraphError(f"{what} : erreur Microsoft {resp.status_code}", resp.status_code)
        return resp.json() if resp.content else {}

    # ── lecture ───────────────────────────────────────────────────────────
    def get_item(self, drive_id: str, item_id: str) -> dict:
        r = self._request("GET", f"{GRAPH}/drives/{quote(drive_id)}/items/{quote(item_id)}")
        return self._check(r, "Lecture du fichier")

    def resolve_share_link(self, url: str) -> dict:
        """Résout un lien de partage OneDrive/SharePoint en driveItem (vérifie l'accès)."""
        if not lien_onedrive_valide(url):
            raise GraphError("Lien OneDrive/SharePoint non reconnu")
        token = "u!" + base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
        r = self._request("GET", f"{GRAPH}/shares/{token}/driveItem")
        return self._check(r, "Vérification du lien")

    def download_stream(self, drive_id: str, item_id: str) -> Iterator[bytes]:
        """Flux binaire. L'URL de téléchargement Graph reste côté serveur."""
        r = self._request("GET", f"{GRAPH}/drives/{quote(drive_id)}/items/{quote(item_id)}/content")
        if r.status_code in (301, 302, 303, 307, 308):
            target = r.headers.get("Location", "")
            if not target.startswith("https://"):
                raise GraphError("Redirection de téléchargement invalide")
            with httpx.stream("GET", target, timeout=httpx.Timeout(300, connect=15)) as dl:
                if dl.status_code != 200:
                    raise GraphError("Téléchargement refusé par Microsoft", dl.status_code)
                for chunk in dl.iter_bytes(1024 * 256):
                    yield chunk
            return
        if r.status_code != 200:
            self._check(r, "Téléchargement")
        yield r.content

    def download_bytes(self, drive_id: str, item_id: str) -> bytes:
        return b"".join(self.download_stream(drive_id, item_id))

    # ── écriture ──────────────────────────────────────────────────────────
    def upload(self, path: str, content: bytes) -> dict:
        """Dépose `content` au chemin relatif (dossiers créés automatiquement). Ne remplace jamais."""
        drive = quote(settings.ONEDRIVE_DRIVE_ID)
        enc = quote(path.strip("/"))
        if len(content) <= _SIMPLE_UPLOAD_MAX:
            r = self._request(
                "PUT", f"{GRAPH}/drives/{drive}/root:/{enc}:/content?@microsoft.graph.conflictBehavior=fail",
                content=content, headers={"Content-Type": "application/octet-stream"},
            )
            return self._check(r, "Envoi vers OneDrive")
        r = self._request("POST", f"{GRAPH}/drives/{drive}/root:/{enc}:/createUploadSession",
                          json={"item": {"@microsoft.graph.conflictBehavior": "fail"}})
        session = self._check(r, "Ouverture de l'envoi")
        upload_url = session["uploadUrl"]
        total = len(content)
        result: dict = {}
        for start in range(0, total, _CHUNK):
            chunk = content[start:start + _CHUNK]
            end = start + len(chunk) - 1
            resp = self.http.put(upload_url, content=chunk, headers={
                "Content-Range": f"bytes {start}-{end}/{total}", "Content-Length": str(len(chunk)),
            }, timeout=120)  # l'URL de session est pré-authentifiée : pas d'en-tête Authorization
            if resp.status_code not in (200, 201, 202):
                raise GraphError("Envoi interrompu par Microsoft", resp.status_code)
            if resp.status_code in (200, 201):
                result = resp.json()
        return result

    # ── détection (delta) ─────────────────────────────────────────────────
    def delta(self, folder_path: str, delta_link: Optional[str]) -> Tuple[List[dict], str]:
        """Retourne (éléments modifiés, nouveau deltaLink). Gère la pagination et resyncRequired."""
        drive = quote(settings.ONEDRIVE_DRIVE_ID)
        url = delta_link or f"{GRAPH}/drives/{drive}/root:/{quote(folder_path.strip('/'))}:/delta"
        if not url.startswith(GRAPH):
            raise GraphError("deltaLink invalide")
        items: List[dict] = []
        while True:
            r = self._request("GET", url)
            if r.status_code == 410:  # resyncRequired : on repart d'une énumération complète
                return self.delta(folder_path, None)
            data = self._check(r, "Synchronisation")
            items.extend(data.get("value", []))
            if "@odata.nextLink" in data:
                url = data["@odata.nextLink"]
                continue
            new_link = data.get("@odata.deltaLink")
            if not new_link:
                raise GraphError("Réponse delta incomplète")
            return items, new_link


def item_metadata(item: Dict) -> Dict:
    return {
        "drive_id": (item.get("parentReference") or {}).get("driveId"),
        "item_id": item.get("id"),
        "nom": item.get("name") or "audio",
        "taille": item.get("size"),
        "mime": (item.get("file") or {}).get("mimeType"),
        "etag": item.get("eTag"),
        "duree_ms": (item.get("audio") or {}).get("duration"),
    }
