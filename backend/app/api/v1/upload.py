"""
Endpoint d'upload de fichiers pour les prestataires (retranscripteurs / correcteurs).
À ajouter dans : backend/app/api/v1/upload.py
"""
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import DbDep, CurrentUser
from app.models.affectation import Affectation, StatutAffectationEnum
from app.models.dossier import Dossier
from app.models.fichier import FichierDossier, TypeDocumentEnum, StatutFichierEnum
from app.models.user import User, RoleEnum
from app.models.journal import TypeActionEnum
from app.schemas.fichier import FichierOut
from app.services.journal import log_action
from app.services import email as email_svc

router = APIRouter()

# Types acceptés
ALLOWED_EXTENSIONS = {".doc", ".docx", ".pdf", ".odt", ".txt", ".mp3", ".wav", ".m4a", ".mp4"}
MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Map rôle prestataire → type de document déposé
_ROLE_TO_TYPE = {
    RoleEnum.RETRANSCRIPTEUR: TypeDocumentEnum.RETRANSCRIPTION_V1,
    RoleEnum.CORRECTEUR:      TypeDocumentEnum.RETRANSCRIPTION_CORRIGEE,
}


def _upload_dir(dossier_id: uuid.UUID) -> Path:
    path = Path(settings.UPLOAD_DIR) / str(dossier_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/dossiers/{dossier_id}/upload", response_model=FichierOut, status_code=201)
async def upload_fichier(
    dossier_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    commentaire: str = Form(default=""),
):
    """
    Dépôt de fichier par un prestataire sur son dossier affecté.
    - Retranscripteur  → type retranscription_v1
    - Correcteur       → type retranscription_corrigee
    Les rôles admin / coordinatrice peuvent uploader n'importe quel type.
    """

    # ── Vérifications ──────────────────────────────────────────────────────
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    # Les prestataires doivent être affectés à ce dossier
    is_presta = current_user.role in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR)
    if is_presta:
        from app.models.prestataire import Prestataire
        presta = db.query(Prestataire).filter(Prestataire.email == current_user.email).first()
        affectation = db.query(Affectation).filter(
            Affectation.dossier_id == dossier_id,
            Affectation.prestataire_id == presta.id if presta else None,
            Affectation.statut == StatutAffectationEnum.EN_COURS,
        ).first() if presta else None
        if not affectation:
            raise HTTPException(
                status_code=403,
                detail="Vous n'avez pas de mission active sur ce dossier",
            )

    # Extension autorisée
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format non autorisé. Formats acceptés : {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Taille maximale
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux (max {settings.MAX_UPLOAD_SIZE_MB} Mo)",
        )

    # ── Sauvegarde physique ────────────────────────────────────────────────
    file_id   = uuid.uuid4()
    safe_name = f"{file_id}{suffix}"
    dest      = _upload_dir(dossier_id) / safe_name
    dest.write_bytes(content)

    # ── Enregistrement en base ─────────────────────────────────────────────
    type_doc = (
        _ROLE_TO_TYPE.get(current_user.role, TypeDocumentEnum.AUTRE)
        if is_presta
        else TypeDocumentEnum.AUTRE
    )

    # Version incrémentale pour ce type de document
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
        url_onedrive=str(dest),   # stockage local ; peut être remplacé par une URL cloud
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
        },
    )
    db.commit()
    db.refresh(fichier)

    # ── Notification email à l'administratrice ─────────────────────────────
    if settings.ADMIN_EMAIL:
        _notify_depot(
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

    # Prestataires : uniquement leurs propres fichiers ou les fichiers audio de leur dossier
    is_presta = current_user.role in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR)
    if is_presta:
        if fichier.uploaded_by_id != current_user.id and fichier.type_document != TypeDocumentEnum.AUDIO_BRUT:
            raise HTTPException(status_code=403, detail="Accès non autorisé")

    path = Path(fichier.url_onedrive)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier physique introuvable")

    return FileResponse(
        path=str(path),
        filename=fichier.nom_fichier,
        media_type="application/octet-stream",
    )


# ── Template email interne ─────────────────────────────────────────────────

def _notify_depot(
    to: str,
    presta_nom: str,
    presta_email: str,
    dossier_ref: str,
    nom_fichier: str,
    type_doc: str,
    version: str,
    commentaire: str,
) -> None:
    from app.services.email import _async, _wrap
    label_map = {
        "retranscription_v1":       "Retranscription (v1)",
        "retranscription_corrigee": "Retranscription corrigée",
        "autre": "Document divers",
    }
    label = label_map.get(type_doc, type_doc)
    comment_row = (
        f"<tr><td style='color:#666;padding:4px 0'>Commentaire</td><td><em>{commentaire}</em></td></tr>"
        if commentaire else ""
    )
    body = _wrap(f"""
      <h2 style="margin:0 0 16px">📎 Nouveau dépôt — {dossier_ref}</h2>
      <p>Un prestataire vient de déposer un fichier sur le dossier <strong>{dossier_ref}</strong>.</p>
      <table style="width:100%;font-size:14px;margin:16px 0">
        <tr><td style="color:#666;padding:4px 0">Prestataire</td><td><strong>{presta_nom}</strong> ({presta_email})</td></tr>
        <tr><td style="color:#666;padding:4px 0">Type</td><td>{label}</td></tr>
        <tr><td style="color:#666;padding:4px 0">Fichier</td><td><code>{nom_fichier}</code></td></tr>
        <tr><td style="color:#666;padding:4px 0">Version</td><td>{version}</td></tr>
        {comment_row}
      </table>
      <p>Connectez-vous au dashboard pour consulter et valider le dépôt.</p>
    """)
    _async(to, f"[A2C] Dépôt reçu — {dossier_ref}", body)
