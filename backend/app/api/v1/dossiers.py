import uuid
from typing import List, Optional
from datetime import date, timezone, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.dossier import Dossier, StatutDossierEnum
from app.models.user import User, RoleEnum
from app.schemas.dossier import DossierCreate, DossierUpdate, DossierQualify, DossierOut, DossierListItem
from app.services.dossier import generate_reference, check_urgence
from app.services.journal import log_action
from app.models.journal import TypeActionEnum

router = APIRouter()


def _check_access(user: User, dossier: Dossier) -> None:
    """Cloisonnement : prestataires accèdent uniquement à leurs dossiers affectés."""
    if user.role in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR):
        assigned_ids = [str(a.dossier_id) for a in user.prestataire_profile.affectations
                        ] if hasattr(user, "prestataire_profile") else []
        if str(dossier.id) not in assigned_ids:
            raise HTTPException(status_code=403, detail="Accès non autorisé à ce dossier")


@router.get("/", response_model=List[DossierListItem])
def list_dossiers(
    db: DbDep,
    current_user: CurrentUser,
    statut: Optional[StatutDossierEnum] = None,
    urgent_only: bool = False,
    client_id: Optional[uuid.UUID] = None,
    limit: int = 100,
    offset: int = 0,
):
    q = db.query(Dossier)

    # Prestataires ne voient que leurs dossiers
    if current_user.role in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR):
        from app.models.affectation import Affectation
        assigned = db.query(Affectation.dossier_id).filter(
            Affectation.prestataire_id == current_user.id
        )
        q = q.filter(Dossier.id.in_(assigned))

    if statut:
        q = q.filter(Dossier.statut == statut)
    if urgent_only:
        q = q.filter(Dossier.est_urgent == True)
    if client_id:
        q = q.filter(Dossier.client_id == client_id)

    # Urgents en tête
    q = q.order_by(Dossier.est_urgent.desc(), Dossier.date_limite.asc().nullslast())
    return q.offset(offset).limit(limit).all()


@router.post("/", response_model=DossierOut, status_code=201)
def create_dossier(
    payload: DossierCreate,
    request: Request,
    db: DbDep,
    current_user: User = Depends(require_admin_or_coordinator),
):
    reference = generate_reference(db, payload.type_instance)
    is_urgent = check_urgence(payload.date_limite)

    dossier = Dossier(
        reference=reference,
        type_instance=payload.type_instance,
        client_id=payload.client_id,
        payeur_id=payload.payeur_id or payload.client_id,
        date_seance=payload.date_seance,
        date_reception_audio=payload.date_reception_audio,
        date_limite=payload.date_limite,
        duree_audio_minutes=payload.duree_audio_minutes,
        niveau_confidentialite=payload.niveau_confidentialite,
        notes_internes=payload.notes_internes,
        titre=payload.titre,
        est_urgent=is_urgent,
    )
    db.add(dossier)
    db.flush()  # get id before commit

    log_action(
        db,
        type_action=TypeActionEnum.CREATION,
        dossier_id=dossier.id,
        utilisateur_id=current_user.id,
        detail={"reference": reference, "type_instance": payload.type_instance.value},
        ip_source=request.client.host if request.client else None,
    )

    db.commit()
    db.refresh(dossier)
    return DossierOut.model_validate(dossier)


@router.get("/{dossier_id}", response_model=DossierOut)
def get_dossier(
    dossier_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    _check_access(current_user, dossier)
    return DossierOut.model_validate(dossier)


@router.patch("/{dossier_id}", response_model=DossierOut)
def update_dossier(
    dossier_id: uuid.UUID,
    payload: DossierUpdate,
    db: DbDep,
    current_user: User = Depends(require_admin_or_coordinator),
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(dossier, field, value)

    db.commit()
    db.refresh(dossier)
    return DossierOut.model_validate(dossier)


@router.post("/{dossier_id}/qualify", response_model=DossierOut)
def qualify_dossier(
    dossier_id: uuid.UUID,
    payload: DossierQualify,
    db: DbDep,
    current_user: User = Depends(require_admin_or_coordinator),
):
    """Étape 2 du workflow — saisie des critères de tarification."""
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if dossier.statut != StatutDossierEnum.RECU:
        raise HTTPException(status_code=400, detail=f"Statut actuel {dossier.statut.value} ne permet pas la qualification")

    dossier.criteres_tarif = payload.criteres_tarif
    dossier.statut = StatutDossierEnum.EN_QUALIFICATION
    if payload.date_limite:
        dossier.date_limite = payload.date_limite
        dossier.est_urgent = check_urgence(payload.date_limite)
    if payload.duree_audio_minutes:
        dossier.duree_audio_minutes = payload.duree_audio_minutes

    log_action(
        db,
        type_action=TypeActionEnum.STATUT,
        dossier_id=dossier.id,
        utilisateur_id=current_user.id,
        detail={"ancien": StatutDossierEnum.RECU.value, "nouveau": StatutDossierEnum.EN_QUALIFICATION.value,
                "criteres": payload.criteres_tarif},
    )

    db.commit()
    db.refresh(dossier)
    return DossierOut.model_validate(dossier)


@router.post("/{dossier_id}/force-urgent", response_model=DossierOut)
def force_urgent(
    dossier_id: uuid.UUID,
    db: DbDep,
    current_user: User = Depends(require_admin_or_coordinator),
):
    """Force manuellement le statut URGENT (avec journalisation)."""
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    dossier.est_urgent = True
    dossier.urgence_forcee = True

    log_action(
        db,
        type_action=TypeActionEnum.STATUT,
        dossier_id=dossier.id,
        utilisateur_id=current_user.id,
        detail={"action": "urgence_forcee", "par": str(current_user.id)},
    )

    db.commit()
    db.refresh(dossier)
    return DossierOut.model_validate(dossier)
