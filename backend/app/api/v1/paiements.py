import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.v1.common import get_dossier
from app.core.deps import DbDep, require_permission
from app.models.dossier import Dossier
from app.models.journal import TypeActionEnum
from app.models.paiement import PaiementPrestataire, StatutPaiementPrestaEnum
from app.models.prestataire import Prestataire
from app.models.pricing.calcul import CalculTarifaire, StatutCalculEnum
from app.models.user import User
from app.services import workflow as wf
from app.services.journal import log_action
from app.services.notifications import notifier, internes

router = APIRouter()


class PaiementUpdate(BaseModel):
    statut: Optional[str] = Field(default=None, pattern="^(a_payer|valide|paye)$")
    date_virement: Optional[date] = None
    reference_virement: Optional[str] = Field(default=None, max_length=100)
    ajustement_manuel: Optional[Decimal] = Field(default=None, ge=-100000, le=100000)
    motif_ajustement: Optional[str] = Field(default=None, max_length=1000)


def paiement_out(db, p: PaiementPrestataire) -> dict:
    presta = db.query(Prestataire).filter(Prestataire.id == p.prestataire_id).first()
    d = db.query(Dossier).filter(Dossier.id == p.dossier_id).first()
    return {
        "id": str(p.id), "dossier_id": str(p.dossier_id), "dossier_reference": d.reference if d else None,
        "prestataire_id": str(p.prestataire_id), "prestataire_nom": presta.nom if presta else None,
        "role_paye": p.role_paye.value, "nombre_pages": p.nombre_pages, "montant_brut": p.montant_brut,
        "ajustement_manuel": p.ajustement_manuel, "motif_ajustement": p.motif_ajustement,
        "montant_final": p.montant_final, "statut": p.statut.value, "date_virement": p.date_virement,
        "reference_virement": p.reference_virement,
    }


@router.get("/paiements-prestataires")
def lister(db: DbDep, _u: User = Depends(require_permission("finance.voir")),
           vue: str = Query(default="a_effectuer", pattern="^(a_effectuer|effectues|tous)$"),
           prestataire_id: Optional[uuid.UUID] = None, limit: int = Query(default=200, ge=1, le=1000)):
    q = db.query(PaiementPrestataire)
    if vue == "a_effectuer":
        q = q.filter(PaiementPrestataire.statut != StatutPaiementPrestaEnum.PAYE)
    elif vue == "effectues":
        q = q.filter(PaiementPrestataire.statut == StatutPaiementPrestaEnum.PAYE)
    if prestataire_id:
        q = q.filter(PaiementPrestataire.prestataire_id == prestataire_id)
    return [paiement_out(db, p) for p in q.limit(limit).all()]


@router.get("/dossiers/{dossier_id}/paiements-prestataires")
def du_dossier(dossier_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("finance.voir"))):
    get_dossier(db, dossier_id)
    return [paiement_out(db, p) for p in db.query(PaiementPrestataire)
            .filter(PaiementPrestataire.dossier_id == dossier_id).all()]


@router.post("/dossiers/{dossier_id}/generer-paiements-prestataires", status_code=201)
def generer(dossier_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("finance.gerer"))):
    from app.api.v1.factures import _generer_paiements
    d = get_dossier(db, dossier_id, lock=True)
    if d.statut_production not in (wf.VALIDE, wf.ARCHIVE):
        raise HTTPException(status_code=409, detail="Le PV doit être validé")
    calcul = db.query(CalculTarifaire).filter(CalculTarifaire.id == d.calcul_tarifaire_id).first() \
        if d.calcul_tarifaire_id else None
    if not calcul or calcul.statut != StatutCalculEnum.DEFINITIF:
        raise HTTPException(status_code=409, detail="Le calcul tarifaire doit être validé")
    nb = _generer_paiements(db, d, calcul)
    log_action(db, TypeActionEnum.PAIEMENT, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "generation_paiements_presta", "nb": nb})
    db.commit()
    return du_dossier(dossier_id, db, user)


@router.patch("/paiements-prestataires/{paiement_id}")
def modifier(paiement_id: uuid.UUID, payload: PaiementUpdate, db: DbDep,
             user: User = Depends(require_permission("finance.gerer"))):
    p = db.query(PaiementPrestataire).filter(PaiementPrestataire.id == paiement_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    if p.statut == StatutPaiementPrestaEnum.PAYE:
        raise HTTPException(status_code=409, detail="Paiement effectué : il n'est plus modifiable")  # fix S19
    changes = payload.model_dump(exclude_unset=True)
    if "ajustement_manuel" in changes:
        if p.statut != StatutPaiementPrestaEnum.A_PAYER:
            raise HTTPException(status_code=409, detail="Ajustement possible uniquement avant validation")
        if not (payload.motif_ajustement or "").strip():
            raise HTTPException(status_code=400, detail="Le motif de l'ajustement est obligatoire")
        p.ajustement_manuel = payload.ajustement_manuel
        p.motif_ajustement = payload.motif_ajustement
        p.montant_final = p.montant_brut + payload.ajustement_manuel
        if p.montant_final < 0:
            raise HTTPException(status_code=400, detail="Le montant final ne peut pas être négatif")
    if payload.reference_virement is not None:
        p.reference_virement = payload.reference_virement
    if payload.date_virement is not None:
        p.date_virement = payload.date_virement
    if payload.statut and payload.statut != p.statut.value:
        wf.verifier_paiement(p.statut.value, payload.statut)
        if payload.statut == "paye" and not p.date_virement:
            raise HTTPException(status_code=400, detail="La date du virement est requise")
        p.statut = StatutPaiementPrestaEnum(payload.statut)
        if payload.statut == "paye":
            notifier(db, internes(db, "finance.voir"), "paiement_effectue", "Paiement prestataire effectué",
                     f"{p.montant_final} € — virement du {p.date_virement:%d/%m/%Y}", lien="/finance",
                     dossier_id=p.dossier_id, exclure=user.id)
    log_action(db, TypeActionEnum.PAIEMENT, dossier_id=p.dossier_id, utilisateur_id=user.id,
               detail={"action": "maj_paiement_presta", "paiement_id": str(p.id),
                       "changements": payload.model_dump(exclude_unset=True, mode="json")})
    db.commit()
    return paiement_out(db, p)
