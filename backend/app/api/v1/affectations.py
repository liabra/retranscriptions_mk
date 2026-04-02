import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.affectation import Affectation, RoleAffectationEnum, StatutAffectationEnum
from app.models.dossier import Dossier, StatutDossierEnum
from app.models.prestataire import Prestataire
from app.models.user import User
from app.schemas.affectation import AffectationCreate, AffectationUpdate, AffectationOut
from app.services.journal import log_action
from app.models.journal import TypeActionEnum

router = APIRouter()


def _get_dossier_or_404(dossier_id: uuid.UUID, db) -> Dossier:
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return dossier


@router.get("/dossiers/{dossier_id}/affectations", response_model=List[AffectationOut])
def list_affectations(
    dossier_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
):
    _get_dossier_or_404(dossier_id, db)
    return db.query(Affectation).filter(Affectation.dossier_id == dossier_id).all()


@router.post("/dossiers/{dossier_id}/affectations", response_model=AffectationOut, status_code=201)
def create_affectation(
    dossier_id: uuid.UUID,
    payload: AffectationCreate,
    db: DbDep,
    _user: User = Depends(require_admin_or_coordinator),
    current_user: CurrentUser = None,
):
    dossier = _get_dossier_or_404(dossier_id, db)

    presta = db.query(Prestataire).filter(Prestataire.id == payload.prestataire_id).first()
    if not presta:
        raise HTTPException(status_code=404, detail="Prestataire introuvable")
    if not presta.actif:
        raise HTTPException(status_code=400, detail="Ce prestataire est inactif")
    if not presta.disponible:
        raise HTTPException(status_code=400, detail="Ce prestataire est indisponible")

    # Interdire le même prestataire sur les deux rôles du même dossier
    existing_roles = db.query(Affectation).filter(
        Affectation.dossier_id == dossier_id,
        Affectation.prestataire_id == payload.prestataire_id,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).all()
    if existing_roles:
        raise HTTPException(
            status_code=400,
            detail="Ce prestataire est déjà affecté à ce dossier",
        )

    # Vérifier qu'il n'y a pas déjà quelqu'un sur ce rôle
    existing_role = db.query(Affectation).filter(
        Affectation.dossier_id == dossier_id,
        Affectation.type_role == payload.type_role,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).first()
    if existing_role:
        raise HTTPException(
            status_code=400,
            detail=f"Un {payload.type_role.value} est déjà affecté à ce dossier",
        )

    affectation = Affectation(
        dossier_id=dossier_id,
        prestataire_id=payload.prestataire_id,
        type_role=payload.type_role,
        date_limite_rendu=payload.date_limite_rendu,
        commentaire=payload.commentaire,
        statut=StatutAffectationEnum.EN_ATTENTE,
    )
    db.add(affectation)

    # Incrémenter la charge du prestataire
    presta.charge_actuelle += 1

    # Mettre à jour le statut du dossier si applicable
    if dossier.statut == StatutDossierEnum.A_ATTRIBUER:
        # Vérifier si les deux rôles sont maintenant couverts
        roles_apres = db.query(Affectation).filter(
            Affectation.dossier_id == dossier_id,
            Affectation.statut != StatutAffectationEnum.REJETE,
        ).count()
        # +1 car la nouvelle affectation n'est pas encore flushée
        if roles_apres + 1 >= 2:
            dossier.statut = StatutDossierEnum.EN_RETRANSCRIPTION
    elif dossier.statut in (StatutDossierEnum.ESTIME, StatutDossierEnum.RECU, StatutDossierEnum.EN_QUALIFICATION):
        dossier.statut = StatutDossierEnum.A_ATTRIBUER

    db.flush()

    log_action(
        db,
        type_action=TypeActionEnum.AFFECTATION,
        dossier_id=dossier_id,
        utilisateur_id=_user.id,
        detail={
            "action": "affectation",
            "prestataire_id": str(payload.prestataire_id),
            "role": payload.type_role.value,
        },
    )
    db.commit()
    db.refresh(affectation)
    return affectation


@router.patch("/affectations/{affectation_id}", response_model=AffectationOut)
def update_affectation(
    affectation_id: uuid.UUID,
    payload: AffectationUpdate,
    db: DbDep,
    _user: User = Depends(require_admin_or_coordinator),
):
    affectation = db.query(Affectation).filter(Affectation.id == affectation_id).first()
    if not affectation:
        raise HTTPException(status_code=404, detail="Affectation introuvable")

    ancien_statut = affectation.statut

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(affectation, field, value)

    # Si l'affectation passe à REJETE, décrémenter la charge
    if payload.statut == StatutAffectationEnum.REJETE and ancien_statut != StatutAffectationEnum.REJETE:
        presta = db.query(Prestataire).filter(Prestataire.id == affectation.prestataire_id).first()
        if presta and presta.charge_actuelle > 0:
            presta.charge_actuelle -= 1

    log_action(
        db,
        type_action=TypeActionEnum.AFFECTATION,
        dossier_id=affectation.dossier_id,
        utilisateur_id=_user.id,
        detail={
            "action": "mise_a_jour_affectation",
            "affectation_id": str(affectation_id),
            "changements": payload.model_dump(exclude_unset=True, mode="json"),
        },
    )
    db.commit()
    db.refresh(affectation)
    return affectation
