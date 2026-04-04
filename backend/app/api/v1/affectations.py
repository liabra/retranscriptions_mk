import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.affectation import Affectation, RoleAffectationEnum, StatutAffectationEnum
from app.models.dossier import Dossier, StatutDossierEnum
from app.models.prestataire import Prestataire
from app.models.user import User, RoleEnum
from app.schemas.affectation import AffectationCreate, AffectationUpdate, AffectationOut, AffectationWithDossierOut
from app.services.journal import log_action
from app.models.journal import TypeActionEnum

router = APIRouter()


def _get_dossier_or_404(dossier_id: uuid.UUID, db) -> Dossier:
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return dossier


def _find_prestataire_by_user(user: User, db) -> Prestataire | None:
    """Trouve le prestataire correspondant à l'utilisateur par email."""
    return db.query(Prestataire).filter(Prestataire.email == user.email).first()


def _auto_transition_dossier(dossier: Dossier, new_statut: StatutDossierEnum, db, user: User, reason: str):
    """Transition automatique du dossier déclenchée par un événement métier."""
    old = dossier.statut
    dossier.statut = new_statut
    log_action(
        db, TypeActionEnum.STATUT,
        dossier_id=dossier.id,
        utilisateur_id=user.id,
        detail={"action": "auto_transition", "de": old.value, "vers": new_statut.value, "raison": reason},
    )


@router.get("/mes-affectations", response_model=List[AffectationWithDossierOut])
def mes_affectations(db: DbDep, current_user: CurrentUser):
    """Retourne les affectations actives du prestataire connecté, avec info dossier."""
    presta = _find_prestataire_by_user(current_user, db)
    if not presta:
        return []
    return (
        db.query(Affectation)
        .filter(
            Affectation.prestataire_id == presta.id,
            Affectation.statut.notin_([StatutAffectationEnum.REJETE]),
        )
        .all()
    )


@router.get("/dossiers/{dossier_id}/affectations", response_model=List[AffectationOut])
def list_affectations(dossier_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
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

    existing_roles = db.query(Affectation).filter(
        Affectation.dossier_id == dossier_id,
        Affectation.prestataire_id == payload.prestataire_id,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).all()
    if existing_roles:
        raise HTTPException(status_code=400, detail="Ce prestataire est déjà affecté à ce dossier")

    existing_role = db.query(Affectation).filter(
        Affectation.dossier_id == dossier_id,
        Affectation.type_role == payload.type_role,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).first()
    if existing_role:
        raise HTTPException(status_code=400, detail=f"Un {payload.type_role.value} est déjà affecté à ce dossier")

    affectation = Affectation(
        dossier_id=dossier_id,
        prestataire_id=payload.prestataire_id,
        type_role=payload.type_role,
        date_limite_rendu=payload.date_limite_rendu,
        commentaire=payload.commentaire,
        statut=StatutAffectationEnum.EN_COURS,  # Directement EN_COURS, pas EN_ATTENTE
    )
    db.add(affectation)
    presta.charge_actuelle += 1

    if dossier.statut == StatutDossierEnum.A_ATTRIBUER:
        roles_apres = db.query(Affectation).filter(
            Affectation.dossier_id == dossier_id,
            Affectation.statut != StatutAffectationEnum.REJETE,
        ).count()
        if roles_apres + 1 >= 2:
            _auto_transition_dossier(dossier, StatutDossierEnum.EN_RETRANSCRIPTION, db, _user, "2 prestataires affectés")
    elif dossier.statut in (StatutDossierEnum.ESTIME, StatutDossierEnum.RECU, StatutDossierEnum.EN_QUALIFICATION):
        dossier.statut = StatutDossierEnum.A_ATTRIBUER

    db.flush()
    log_action(
        db, TypeActionEnum.AFFECTATION,
        dossier_id=dossier_id,
        utilisateur_id=_user.id,
        detail={"action": "affectation", "prestataire_id": str(payload.prestataire_id), "role": payload.type_role.value},
    )
    db.commit()
    db.refresh(affectation)
    return affectation


@router.patch("/affectations/{affectation_id}", response_model=AffectationOut)
def update_affectation(
    affectation_id: uuid.UUID,
    payload: AffectationUpdate,
    db: DbDep,
    current_user: CurrentUser,
):
    affectation = db.query(Affectation).filter(Affectation.id == affectation_id).first()
    if not affectation:
        raise HTTPException(status_code=404, detail="Affectation introuvable")

    is_admin_or_coord = current_user.role in (RoleEnum.ADMINISTRATRICE, RoleEnum.COORDINATRICE)
    if not is_admin_or_coord:
        # Prestataire ne peut modifier que sa propre affectation, uniquement vers LIVRE
        presta = _find_prestataire_by_user(current_user, db)
        if not presta or presta.id != affectation.prestataire_id:
            raise HTTPException(status_code=403, detail="Accès refusé")
        if payload.statut and payload.statut != StatutAffectationEnum.LIVRE:
            raise HTTPException(status_code=403, detail="Vous pouvez uniquement marquer votre travail comme livré")

    ancien_statut = affectation.statut

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(affectation, field, value)

    if payload.statut == StatutAffectationEnum.REJETE and ancien_statut != StatutAffectationEnum.REJETE:
        presta = db.query(Prestataire).filter(Prestataire.id == affectation.prestataire_id).first()
        if presta and presta.charge_actuelle > 0:
            presta.charge_actuelle -= 1

    # Auto-transitions dossier selon événement affectation
    if payload.statut and payload.statut != ancien_statut:
        dossier = db.query(Dossier).filter(Dossier.id == affectation.dossier_id).first()
        if dossier:
            if (affectation.type_role == RoleAffectationEnum.RETRANSCRIPTEUR
                    and payload.statut == StatutAffectationEnum.LIVRE
                    and dossier.statut == StatutDossierEnum.EN_RETRANSCRIPTION):
                _auto_transition_dossier(dossier, StatutDossierEnum.A_CORRIGER, db, current_user, "retranscripteur a livré")

            elif (affectation.type_role == RoleAffectationEnum.CORRECTEUR
                    and payload.statut == StatutAffectationEnum.EN_COURS
                    and dossier.statut == StatutDossierEnum.A_CORRIGER):
                _auto_transition_dossier(dossier, StatutDossierEnum.EN_CORRECTION, db, current_user, "correcteur a commencé")

            elif (affectation.type_role == RoleAffectationEnum.CORRECTEUR
                    and payload.statut == StatutAffectationEnum.LIVRE
                    and dossier.statut in (StatutDossierEnum.EN_CORRECTION, StatutDossierEnum.A_CORRIGER)):
                _auto_transition_dossier(dossier, StatutDossierEnum.EN_MISE_EN_FORME, db, current_user, "correcteur a livré")

    log_action(
        db, TypeActionEnum.AFFECTATION,
        dossier_id=affectation.dossier_id,
        utilisateur_id=current_user.id,
        detail={
            "action": "mise_a_jour_affectation",
            "affectation_id": str(affectation_id),
            "changements": payload.model_dump(exclude_unset=True, mode="json"),
        },
    )
    db.commit()
    db.refresh(affectation)
    return affectation
