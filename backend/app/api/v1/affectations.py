"""
Attribution des missions — toujours décidée par une responsable (aucune attribution automatique).
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.common import get_dossier, AFF_ACTIVES
from app.core.deps import DbDep, require_permission
from app.models.affectation import Affectation, RoleAffectationEnum, StatutAffectationEnum
from app.models.journal import TypeActionEnum
from app.models.prestataire import Prestataire, RolePrestaEnum
from app.models.user import User
from app.services import delais, workflow as wf
from app.services.attribution import suggestions, charge_reelle
from app.services.journal import log_action
from app.services.notifications import notifier, compte_prestataire

router = APIRouter()


class AttributionCreate(BaseModel):
    prestataire_id: uuid.UUID
    date_limite_rendu: Optional[datetime] = None
    commentaire: Optional[str] = Field(default=None, max_length=2000)  # consignes visibles du prestataire
    confirmer_indisponible: bool = False


class AttributionUpdate(BaseModel):
    date_limite_rendu: Optional[datetime] = None
    commentaire: Optional[str] = Field(default=None, max_length=2000)


class Retrait(BaseModel):
    motif: str = Field(min_length=3, max_length=1000)


@router.get("/dossiers/{dossier_id}/suggestions")
def suggerer(dossier_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("attribution.gerer"))):
    d = get_dossier(db, dossier_id)
    return {"dossier_id": str(d.id), "type_instance": d.type_instance.value,
            "avertissement": "Suggestions indicatives : la décision appartient à la responsable.",
            "suggestions": suggestions(db, d)}


@router.post("/dossiers/{dossier_id}/affectations", status_code=201)
def attribuer(dossier_id: uuid.UUID, payload: AttributionCreate, db: DbDep,
              user: User = Depends(require_permission("attribution.gerer"))):
    d = get_dossier(db, dossier_id, lock=True)
    if d.statut_production != wf.A_ATTRIBUER:
        raise HTTPException(status_code=409, detail="Le dossier doit être qualifié et « à attribuer »")
    presta = db.query(Prestataire).filter(Prestataire.id == payload.prestataire_id).first()
    if not presta or not presta.actif or presta.role == RolePrestaEnum.CORRECTEUR:
        raise HTTPException(status_code=400, detail="Retranscripteur introuvable ou inactif")
    if not presta.disponible and not payload.confirmer_indisponible:
        raise HTTPException(status_code=409, detail="Ce retranscripteur est indiqué indisponible : confirmez l'attribution")
    if db.query(Affectation).filter(Affectation.dossier_id == d.id, Affectation.statut.in_(AFF_ACTIVES)).first():
        raise HTTPException(status_code=409, detail="Une attribution est déjà active sur ce dossier")
    echeance = payload.date_limite_rendu or delais.echeance_retranscripteur(db, d.date_limite)
    aff = Affectation(
        dossier_id=d.id, prestataire_id=presta.id, type_role=RoleAffectationEnum.RETRANSCRIPTEUR,
        date_limite_rendu=echeance, commentaire=payload.commentaire, statut=StatutAffectationEnum.EN_ATTENTE,
    )
    db.add(aff)
    db.flush()
    wf.changer_production(db, d, wf.ATTRIBUE, user.id, extra={"prestataire_id": str(presta.id)})
    delais.figer(db, d, user.id)  # l'échéance client devient définitive (historisée)
    db.flush()
    presta.charge_actuelle = charge_reelle(db, presta.id)  # fix B7 : charge recalculée
    log_action(db, TypeActionEnum.AFFECTATION, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "attribution", "prestataire_id": str(presta.id), "affectation_id": str(aff.id),
                       "echeance_retranscripteur": echeance.isoformat() if echeance else None,
                       "echeance_client": d.date_limite.isoformat() if d.date_limite else None})
    notifier(db, compte_prestataire(db, presta.id), "mission_attribuee",
             f"Nouvelle mission : {d.reference}",
             "Une nouvelle retranscription vous a été attribuée"
             + (f" (échéance le {echeance:%d/%m/%Y})." if echeance else "."),
             lien="/mes-missions", dossier_id=d.id, dedup_key=f"attribution:{aff.id}")
    db.commit()
    return {"id": str(aff.id), "statut": aff.statut.value, "date_limite_rendu": aff.date_limite_rendu}


@router.patch("/affectations/{affectation_id}")
def modifier(affectation_id: uuid.UUID, payload: AttributionUpdate, db: DbDep,
             user: User = Depends(require_permission("attribution.gerer"))):
    """fix S6 : seules les responsables modifient échéance et consignes."""
    aff = db.query(Affectation).filter(Affectation.id == affectation_id).first()
    if not aff or aff.statut not in AFF_ACTIVES:
        raise HTTPException(status_code=404, detail="Attribution active introuvable")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(aff, k, v)
    log_action(db, TypeActionEnum.AFFECTATION, dossier_id=aff.dossier_id, utilisateur_id=user.id,
               detail={"action": "modification_attribution", "affectation_id": str(aff.id),
                       "changements": {k: str(v) for k, v in changes.items()}})
    if "date_limite_rendu" in changes:
        notifier(db, compte_prestataire(db, aff.prestataire_id), "echeance_modifiee",
                 "Échéance modifiée",
                 f"Nouvelle échéance : {aff.date_limite_rendu:%d/%m/%Y}" if aff.date_limite_rendu else None,
                 lien="/mes-missions", dossier_id=aff.dossier_id)
    db.commit()
    return {"id": str(aff.id), "date_limite_rendu": aff.date_limite_rendu, "commentaire": aff.commentaire}


@router.post("/affectations/{affectation_id}/retirer")
def retirer(affectation_id: uuid.UUID, payload: Retrait, db: DbDep,
            user: User = Depends(require_permission("attribution.gerer"))):
    aff = db.query(Affectation).filter(Affectation.id == affectation_id).first()
    if not aff or aff.statut not in AFF_ACTIVES:
        raise HTTPException(status_code=404, detail="Attribution active introuvable")
    d = get_dossier(db, aff.dossier_id, lock=True)
    if d.statut_production not in (wf.ATTRIBUE, wf.EN_COURS, wf.CORRECTION_DEMANDEE):
        raise HTTPException(status_code=409, detail="Le retrait n'est possible que pendant la production")
    aff.statut = StatutAffectationEnum.REJETE
    wf.changer_production(db, d, wf.A_ATTRIBUER, user.id, payload.motif)
    presta = db.query(Prestataire).filter(Prestataire.id == aff.prestataire_id).first()
    if presta:
        db.flush()
        presta.charge_actuelle = charge_reelle(db, presta.id)
    log_action(db, TypeActionEnum.AFFECTATION, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "retrait_attribution", "affectation_id": str(aff.id), "motif": payload.motif})
    notifier(db, compte_prestataire(db, aff.prestataire_id), "mission_retiree",
             f"Mission {d.reference} retirée", "Cette mission ne vous est plus attribuée.",
             lien="/mes-missions", dossier_id=d.id)
    db.commit()
    return {"id": str(aff.id), "statut": aff.statut.value}
