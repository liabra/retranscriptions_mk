import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser
from app.models.dossier import Dossier
from app.models.fichier import FichierDossier, StatutFichierEnum
from app.models.user import User, RoleEnum
from app.schemas.fichier import FichierCreate, FichierUpdate, FichierOut
from app.services.journal import log_action
from app.models.journal import TypeActionEnum

router = APIRouter()

# Rôles qui peuvent voir tous les fichiers d'un dossier
_ROLES_FULL_ACCESS = {RoleEnum.ADMINISTRATRICE, RoleEnum.COORDINATRICE, RoleEnum.COMPTABILITE}

# Types de documents visibles par les prestataires
_TYPES_PRESTATAIRE = {"audio_brut", "retranscription_v1", "retranscription_corrigee"}


def _get_dossier_or_404(dossier_id: uuid.UUID, db) -> Dossier:
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return dossier


@router.get("/dossiers/{dossier_id}/fichiers", response_model=List[FichierOut])
def list_fichiers(
    dossier_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
):
    _get_dossier_or_404(dossier_id, db)
    q = db.query(FichierDossier).filter(
        FichierDossier.dossier_id == dossier_id,
        FichierDossier.statut != StatutFichierEnum.OBSOLETE,
    )
    # Prestataires : uniquement les fichiers utiles à leur mission
    if current_user.role in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR):
        q = q.filter(FichierDossier.type_document.in_(_TYPES_PRESTATAIRE))
    return q.order_by(FichierDossier.created_at.desc()).all()


@router.post("/dossiers/{dossier_id}/fichiers", response_model=FichierOut, status_code=201)
def add_fichier(
    dossier_id: uuid.UUID,
    payload: FichierCreate,
    db: DbDep,
    current_user: CurrentUser,
):
    _get_dossier_or_404(dossier_id, db)

    fichier = FichierDossier(
        dossier_id=dossier_id,
        uploaded_by_id=current_user.id,
        type_document=payload.type_document,
        nom_fichier=payload.nom_fichier,
        url_onedrive=payload.url_onedrive,
        version=payload.version,
        commentaire=payload.commentaire,
    )
    db.add(fichier)
    db.flush()

    log_action(
        db,
        type_action=TypeActionEnum.ACCES_DOCUMENT,
        dossier_id=dossier_id,
        utilisateur_id=current_user.id,
        detail={
            "action": "ajout_fichier",
            "nom": payload.nom_fichier,
            "type": payload.type_document.value,
            "version": payload.version,
        },
    )
    db.commit()
    db.refresh(fichier)
    return fichier


@router.patch("/fichiers/{fichier_id}", response_model=FichierOut)
def update_fichier(
    fichier_id: uuid.UUID,
    payload: FichierUpdate,
    db: DbDep,
    current_user: CurrentUser,
):
    fichier = db.query(FichierDossier).filter(FichierDossier.id == fichier_id).first()
    if not fichier:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    # Seul l'auteur ou admin/coord peut modifier
    if current_user.role not in _ROLES_FULL_ACCESS and fichier.uploaded_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Modification non autorisée")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(fichier, field, value)

    log_action(
        db,
        type_action=TypeActionEnum.ACCES_DOCUMENT,
        dossier_id=fichier.dossier_id,
        utilisateur_id=current_user.id,
        detail={
            "action": "modification_fichier",
            "fichier_id": str(fichier_id),
            "changements": payload.model_dump(exclude_unset=True, mode="json"),
        },
    )
    db.commit()
    db.refresh(fichier)
    return fichier
