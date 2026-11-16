import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.common import get_dossier
from app.core.deps import DbDep, require_permission
from app.models.facture import FactureClient
from app.models.journal import TypeActionEnum
from app.models.pricing.calcul import CalculTarifaire, StatutCalculEnum
from app.models.user import User
from app.schemas.calcul import CalculAjustement, CalculOut
from app.services.calcul_service import run_calcul
from app.services.journal import log_action

router = APIRouter()


class CalculTrigger(BaseModel):
    nombre_pages: Optional[Decimal] = Field(default=None, gt=0, le=5000)


def _calcul(db, calcul_id: uuid.UUID) -> CalculTarifaire:
    c = db.query(CalculTarifaire).filter(CalculTarifaire.id == calcul_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Calcul introuvable")
    return c


def _facture_active(db, dossier_id) -> Optional[FactureClient]:
    return db.query(FactureClient).filter(FactureClient.dossier_id == dossier_id,
                                          FactureClient.annulee_le.is_(None)).first()


@router.post("/dossiers/{dossier_id}/calculer", response_model=CalculOut, status_code=201)
def calculer(dossier_id: uuid.UUID, payload: CalculTrigger, db: DbDep,
             user: User = Depends(require_permission("finance.gerer"))):
    d = get_dossier(db, dossier_id, lock=True)
    if _facture_active(db, d.id):  # fix : jamais de recalcul après facturation (pas de rétroactivité)
        raise HTTPException(status_code=409, detail="Dossier facturé : le calcul est figé")
    pages = payload.nombre_pages or d.nombre_pages_final
    if not pages:
        raise HTTPException(status_code=400, detail="Nombre de pages requis (renseigné à la validation du PV)")
    calcul = run_calcul(d, Decimal(str(pages)), user.id, db)
    db.commit()
    db.refresh(calcul)
    return calcul


@router.get("/dossiers/{dossier_id}/calculs", response_model=List[CalculOut])
def lister(dossier_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("finance.voir"))):
    get_dossier(db, dossier_id)
    return db.query(CalculTarifaire).filter(CalculTarifaire.dossier_id == dossier_id) \
        .order_by(CalculTarifaire.version_calcul.desc()).all()


@router.get("/calculs/{calcul_id}", response_model=CalculOut)
def lire(calcul_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("finance.voir"))):
    return _calcul(db, calcul_id)


@router.post("/calculs/{calcul_id}/valider", response_model=CalculOut)
def valider(calcul_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("finance.gerer"))):
    calcul = _calcul(db, calcul_id)
    d = get_dossier(db, calcul.dossier_id, lock=True)
    if calcul.statut == StatutCalculEnum.DEFINITIF:
        raise HTTPException(status_code=409, detail="Ce calcul est déjà validé")
    if d.calcul_tarifaire_id != calcul.id:
        raise HTTPException(status_code=409, detail="Seul le calcul le plus récent peut être validé")
    if calcul.montant_client_final <= 0:
        raise HTTPException(status_code=409, detail="Montant client nul : vérifiez les grilles avant de valider")
    ancien = calcul.statut.value
    calcul.statut = StatutCalculEnum.DEFINITIF
    calcul.valide_par_id = user.id
    # fix B4 : la validation financière ne modifie plus l'étape de production
    log_action(db, TypeActionEnum.CALCUL_TARIFAIRE, dossier_id=calcul.dossier_id, utilisateur_id=user.id,
               detail={"action": "validation_calcul", "calcul_id": str(calcul.id), "ancien_statut": ancien,
                       "montant_client_final": str(calcul.montant_client_final)})
    db.commit()
    db.refresh(calcul)
    return calcul


@router.post("/calculs/{calcul_id}/ajuster", response_model=CalculOut)
def ajuster(calcul_id: uuid.UUID, payload: CalculAjustement, db: DbDep,
            user: User = Depends(require_permission("finance.gerer"))):
    calcul = _calcul(db, calcul_id)
    if calcul.statut == StatutCalculEnum.DEFINITIF:
        raise HTTPException(status_code=409, detail="Impossible d'ajuster un calcul validé. Recalculez.")
    if not (payload.motif_ajustement_client or "").strip():
        raise HTTPException(status_code=400, detail="Le motif de l'ajustement est obligatoire")
    ancien = calcul.montant_client_final
    calcul.ajustement_client = payload.ajustement_client
    calcul.motif_ajustement_client = payload.motif_ajustement_client
    calcul.montant_client_final = calcul.montant_client_brut + payload.ajustement_client
    if calcul.montant_client_final < 0:
        raise HTTPException(status_code=400, detail="Le montant final ne peut pas être négatif")
    calcul.marge_brute = calcul.montant_client_final - calcul.montant_prestataires_total
    calcul.statut = StatutCalculEnum.AJUSTE
    log_action(db, TypeActionEnum.AJUSTEMENT_TARIFAIRE, dossier_id=calcul.dossier_id, utilisateur_id=user.id,
               detail={"action": "ajustement_calcul", "calcul_id": str(calcul_id), "montant_avant": str(ancien),
                       "ajustement": str(payload.ajustement_client), "montant_apres": str(calcul.montant_client_final),
                       "motif": payload.motif_ajustement_client})
    db.commit()
    db.refresh(calcul)
    return calcul
