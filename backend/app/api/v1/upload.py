"""
Endpoints d'upload de fichiers.

- Prestataires (retranscripteur / correcteur) : dépôt Word/PDF/ODT sur leur dossier affecté
- Clients (role CLIENT) : dépôt audio (MP3, WAV, M4A, MP4) sur leurs dossiers

OneDrive (Microsoft Graph) est utilisé si ONEDRIVE_* est configuré ; sinon stockage local.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import DbDep, CurrentUser
from app.models.affectation import Affectation, StatutAffectationEnum
from app.models.client import Client
from app.models.dossier import Dossier
from app.models.fichier import FichierDossier, TypeDocumentEnum, StatutFichierEnum
from app.models.prestataire import Prestataire
from app.models.user import RoleEnum
from app.models.journal import TypeActionEnum
from app.schemas.fichier import FichierOut
from app.services import email as email_svc
from app.services import onedrive as onedrive_svc
from app.services.journal import log_action

router = APIRouter()

# ── Constantes ────────────────────────────────────────────────────────────────

PRESTA_EXTENSIONS = {".doc", ".docx", ".pdf", ".odt", ".txt"}
AUDIO_EXTENSIONS  = {".mp3", ".wav", ".m4a", ".mp4"}
ALLOWED_EXTENSIONS = PRESTA_EXTENSIONS | AUDIO_EXTENSIONS

MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

_ROLE_TO_TYPE = {
    RoleEnum.RETRANSCRIPTEUR: TypeDocumentEnum.RETRANSCRIPTION_V1,
    RoleEnum.CORRECTEUR:      TypeDocumentEnum.RETRANSCRIPTION_CORRIGEE,
    RoleEnum.CLIENT:          TypeDocumentEnum.AUDIO_BRUT,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _local_upload_dir(dossier_id: uuid.UUID) -> Path:
    path = Path(settings.UPLOAD_DIR) / str(dossier_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_file(content: bytes, filename: str, dossier_id: uuid.UUID,
               onedrive_folder: "str | None") -> str:
    """
    Sauvegarde le fichier : OneDrive si configuré, sinon local.
    Retourne la référence (URL OneDrive ou chemin local absolu).
    """
    if onedrive_folder:
        url = onedrive_svc.upload_file(content, filename, onedrive_folder)
        if url:
            return url
        # Fallback silencieux vers local si OneDrive échoue

    dest = _local_upload_dir(dossier_id) / filename
    dest.write_bytes(content)
    return str(dest)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/dossiers/{dossier_id}/upload", response_model=FichierOut, status_code=201)
async def upload_fichier(
    dossier_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    commentaire: str = Form(default=""),
):
    """
    Dépôt de fichier sur un dossier.

    - Retranscripteur  → retranscription_v1 (Word/PDF uniquement)
    - Correcteur       → retranscription_corrigee (Word/PDF uniquement)
    - Client           → audio_brut (MP3/WAV/M4A/MP4 uniquement)
    - Admin/coordinatrice → tout type accepté
    """
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    is_presta  = current_user.role in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR)
    is_client  = current_user.role == RoleEnum.CLIENT
    is_admin   = current_user.role in (RoleEnum.ADMINISTRATRICE, RoleEnum.COORDINATRICE)

    suffix = Path(file.filename or "").suffix.lower()

    # ── Vérification accès & extensions autorisées ────────────────────────────

    if is_presta:
        presta = db.query(Prestataire).filter(Prestataire.email == current_user.email).first()
        affectation = (
            db.query(Affectation).filter(
                Affectation.dossier_id == dossier_id,
                Affectation.prestataire_id == presta.id,
                Affectation.statut == StatutAffectationEnum.EN_COURS,
            ).first()
            if presta else None
        )
        if not affectation:
            raise HTTPException(status_code=403, detail="Vous n'avez pas de mission active sur ce dossier")
        if suffix not in PRESTA_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Format non autorisé. Formats acceptés : {', '.join(sorted(PRESTA_EXTENSIONS))}",
            )

    elif is_client:
        client = db.query(Client).filter(Client.email_contact == current_user.email).first()
        if not client or dossier.client_id != client.id:
            raise HTTPException(status_code=403, detail="Ce dossier ne vous appartient pas")
        if suffix not in AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Format audio uniquement. Formats acceptés : {', '.join(sorted(AUDIO_EXTENSIONS))}",
            )

    elif not is_admin:
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    else:  # admin/coord → toutes extensions
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Format non autorisé. Formats acceptés : {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

    # ── Lecture + vérification taille ─────────────────────────────────────────
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux (max {settings.MAX_UPLOAD_SIZE_MB} Mo)",
        )

    # ── Détermination type document + dossier OneDrive ────────────────────────
    type_doc = _ROLE_TO_TYPE.get(current_user.role, TypeDocumentEnum.AUTRE)

    onedrive_folder: "str | None" = None
    if is_presta:
        onedrive_folder = f"{settings.ONEDRIVE_PRESTATAIRE_FOLDER}/{dossier_id}"
    elif is_client:
        onedrive_folder = f"{settings.ONEDRIVE_AUDIO_FOLDER}/{dossier_id}"
    elif is_admin and settings.ONEDRIVE_DRIVE_ID:
        onedrive_folder = f"Admin/{dossier_id}"

    # ── Sauvegarde physique ────────────────────────────────────────────────────
    file_id   = uuid.uuid4()
    safe_name = f"{file_id}{suffix}"
    url_ref   = _save_file(content, safe_name, dossier_id, onedrive_folder)

    # ── Enregistrement en base ─────────────────────────────────────────────────
    existing_count = db.query(FichierDossier).filter(
        FichierDossier.dossier_id == dossier_id,
        FichierDossier.type_document == type_doc,
    ).count()
    version = f"{existing_count + 1}.0"

    fichier = FichierDossier(
        id=file_id,
        dossier_id=dossier_id,
        uploaded_by_id=current_user.id,
        type_document=type_doc,
        nom_fichier=file.filename or safe_name,
        url_onedrive=url_ref,
        version=version,
        statut=StatutFichierEnum.DISPONIBLE,
        commentaire=commentaire or None,
    )
    db.add(fichier)
    db.flush()

    log_action(
        db,
        type_action=TypeActionEnum.ACCES_DOCUMENT,
        dossier_id=dossier_id,
        utilisateur_id=current_user.id,
        detail={
            "action": "upload_fichier",
            "nom": file.filename,
            "type": type_doc.value,
            "version": version,
            "taille_ko": round(len(content) / 1024, 1),
            "stockage": "onedrive" if url_ref.startswith("http") else "local",
        },
    )
    db.commit()
    db.refresh(fichier)

    # ── Notifications email ────────────────────────────────────────────────────
    if settings.ADMIN_EMAIL:
        if is_client:
            client_obj = db.query(Client).filter(Client.email_contact == current_user.email).first()
            email_svc.send_depot_audio_client(
                to=settings.ADMIN_EMAIL,
                client_nom=current_user.nom,
                client_email=current_user.email,
                dossier_ref=dossier.reference,
                nom_fichier=file.filename or safe_name,
                taille_ko=round(len(content) / 1024, 1),
                commentaire=commentaire,
            )
        else:
            email_svc.send_depot_prestataire(
                to=settings.ADMIN_EMAIL,
                presta_nom=current_user.nom,
                presta_email=current_user.email,
                dossier_ref=dossier.reference,
                nom_fichier=file.filename or safe_name,
                type_doc=type_doc.value,
                version=version,
                commentaire=commentaire,
            )

    return fichier


@router.get("/fichiers/{fichier_id}/download")
def download_fichier(
    fichier_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
):
    """Téléchargement d'un fichier — accès sécurisé par rôle."""
    fichier = db.query(FichierDossier).filter(FichierDossier.id == fichier_id).first()
    if not fichier:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    is_presta = current_user.role in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR)
    is_client = current_user.role == RoleEnum.CLIENT

    # Prestataires : leurs propres fichiers ou fichiers audio de leur dossier
    if is_presta:
        if fichier.uploaded_by_id != current_user.id and fichier.type_document != TypeDocumentEnum.AUDIO_BRUT:
            raise HTTPException(status_code=403, detail="Accès non autorisé")

    # Clients : uniquement leurs propres fichiers
    elif is_client:
        if fichier.uploaded_by_id != current_user.id:
            raise HTTPException(status_code=403, detail="Accès non autorisé")

    # Si le fichier est sur OneDrive (URL http), rediriger
    if fichier.url_onedrive and fichier.url_onedrive.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=fichier.url_onedrive)

    path = Path(fichier.url_onedrive)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier physique introuvable")

    return FileResponse(
        path=str(path),
        filename=fichier.nom_fichier,
        media_type="application/octet-stream",
    )


