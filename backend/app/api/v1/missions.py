import uuid
from datetime import date
from typing import List

from fastapi import APIRouter, HTTPException

from app.core.deps import DbDep, CurrentUser
from app.models.affectation import Affectation, StatutAffectationEnum
from app.models.dossier import Dossier
from app.models.fichier import FichierDossier, TypeDocumentEnum
from app.models.user import RoleEnum
from app.models.prestataire import Prestataire
from app.models.journal import TypeActionEnum
from app.services.journal import log_action

router = APIRouter()


def _get_presta_for_user(current_user, db) -> Prestataire:
    presta = db.query(Prestataire).filter(
        Prestataire.email == current_user.email,
        Prestataire.actif == True,  # noqa: E712
    ).first()
    if not presta:
        raise HTTPException(
            status_code=404,
            detail="Aucun profil prestataire trouvé pour cet utilisateur",
        )
    return presta


@router.get("/missions/mes-dossiers")
def mes_dossiers(db: DbDep, current_user: CurrentUser):
    if current_user.role not in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR):
        raise HTTPException(status_code=403, detail="Réservé aux prestataires")

    presta = _get_presta_for_user(current_user, db)

    affectations = db.query(Affectation).filter(
        Affectation.prestataire_id == presta.id,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).all()

    if not affectations:
        return []

    dossier_ids = [a.dossier_id for a in affectations]
    dossiers = db.query(Dossier).filter(Dossier.id.in_(dossier_ids)).all()

    result = []
    for d in dossiers:
        aff = next((a for a in affectations if a.dossier_id == d.id), None)
        result.append({
            "id": str(d.id),
            "reference": d.reference,
            "titre": d.titre,
            "statut": d.statut.value,
            "type_instance": d.type_instance.value,
            "date_limite": d.date_limite.isoformat() if d.date_limite else None,
            "est_urgent": d.est_urgent,
            "affectation_id": str(aff.id) if aff else None,
            "role": aff.type_role.value if aff else None,
            "statut_affectation": aff.statut.value if aff else None,
            "date_limite_rendu": aff.date_limite_rendu.isoformat() if aff and aff.date_limite_rendu else None,
        })
    return result


@router.post("/affectations/{affectation_id}/livrer")
def declarer_livraison(
    affectation_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
):
    if current_user.role not in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR):
        raise HTTPException(status_code=403, detail="Réservé aux prestataires")

    affectation = db.query(Affectation).filter(Affectation.id == affectation_id).first()
    if not affectation:
        raise HTTPException(status_code=404, detail="Affectation introuvable")

    presta = _get_presta_for_user(current_user, db)
    if affectation.prestataire_id != presta.id:
        raise HTTPException(status_code=403, detail="Cette affectation ne vous appartient pas")

    if affectation.statut not in (
        StatutAffectationEnum.EN_ATTENTE, StatutAffectationEnum.EN_COURS
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de livrer depuis le statut : {affectation.statut.value}",
        )

    affectation.statut = StatutAffectationEnum.LIVRE
    affectation.date_rendu_effectif = date.today()

    log_action(
        db, TypeActionEnum.AFFECTATION,
        dossier_id=affectation.dossier_id,
        utilisateur_id=current_user.id,
        detail={
            "action": "livraison",
            "affectation_id": str(affectation_id),
            "role": affectation.type_role.value,
        },
    )
    db.commit()
    db.refresh(affectation)
    return {
        "statut": affectation.statut.value,
        "date_rendu_effectif": str(affectation.date_rendu_effectif),
    }


@router.get("/missions/fichiers/{dossier_id}")
def fichiers_mission(
    dossier_id: uuid.UUID,
    db: DbDep,
    current_user: CurrentUser,
):
    if current_user.role not in (RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR):
        raise HTTPException(status_code=403, detail="Réservé aux prestataires")

    presta = _get_presta_for_user(current_user, db)

    aff = db.query(Affectation).filter(
        Affectation.dossier_id == dossier_id,
        Affectation.prestataire_id == presta.id,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).first()
    if not aff:
        raise HTTPException(status_code=403, detail="Vous n'êtes pas affecté à ce dossier")

    types_autorises = [
        TypeDocumentEnum.AUDIO_BRUT,
        TypeDocumentEnum.RETRANSCRIPTION_V1,
        TypeDocumentEnum.RETRANSCRIPTION_CORRIGEE,
    ]
    return db.query(FichierDossier).filter(
        FichierDossier.dossier_id == dossier_id,
        FichierDossier.type_document.in_(types_autorises),
    ).all()
