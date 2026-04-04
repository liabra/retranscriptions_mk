import uuid
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.dossier import Dossier, StatutDossierEnum
from app.models.affectation import Affectation, StatutAffectationEnum, RoleAffectationEnum
from app.models.pricing.calcul import CalculTarifaire, StatutCalculEnum
from app.models.user import User
from app.models.journal import TypeActionEnum
from app.schemas.calcul import CalculTrigger, CalculAjustement, CalculOut
from app.services.pricing.engine import PricingEngine
from app.services.journal import log_action
from app.services.calcul_service import run_calcul, _forfait_a2c as _forfait

router = APIRouter()


def _forfait_a2c(nombre_pages: Decimal) -> Decimal:
    """
    Forfait client A2C par tranche de pages — table officielle.
    Utilisé en fallback si aucune grille CLIENT active n'est configurée.
    """
    p = float(nombre_pages)
    if p <= 0:
        return Decimal("0.00")
    if p <= 9:
        return Decimal("50.00")
    if p <= 20:
        return Decimal("100.00")
    if p <= 30:
        return Decimal("150.00")
    if p <= 40:
        return Decimal("200.00")
    if p <= 50:
        return Decimal("250.00")
    if p <= 60:
        return Decimal("300.00")
    if p <= 70:
        return Decimal("350.00")
    if p <= 80:
        return Decimal("400.00")
    if p <= 90:
        return Decimal("450.00")
    if p <= 100:
        return Decimal("500.00")
    # Au-delà de 100 pages : 5 €/page (taux moyen)
    return (Decimal(str(p)) * Decimal("5.00")).quantize(Decimal("0.01"))


def _get_dossier_or_404(dossier_id: uuid.UUID, db) -> Dossier:
    d = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return d


def _get_calcul_or_404(calcul_id: uuid.UUID, db) -> CalculTarifaire:
    c = db.query(CalculTarifaire).filter(CalculTarifaire.id == calcul_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Calcul introuvable")
    return c


@router.post("/dossiers/{dossier_id}/calculer", response_model=CalculOut, status_code=201)
def calculer_dossier(
    dossier_id: uuid.UUID,
    payload: CalculTrigger,
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
):
    dossier = _get_dossier_or_404(dossier_id, db)
    calcul = run_calcul(dossier, payload.nombre_pages, admin.id, db)
    db.commit()
    db.refresh(calcul)
    return calcul


@router.get("/dossiers/{dossier_id}/calculs", response_model=List[CalculOut])
def list_calculs(dossier_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    _get_dossier_or_404(dossier_id, db)
    return (
        db.query(CalculTarifaire)
        .filter(CalculTarifaire.dossier_id == dossier_id)
        .order_by(CalculTarifaire.version_calcul.desc())
        .all()
    )


@router.get("/calculs/{calcul_id}", response_model=CalculOut)
def get_calcul(calcul_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    return _get_calcul_or_404(calcul_id, db)


@router.post("/calculs/{calcul_id}/valider", response_model=CalculOut)
def valider_calcul(
    calcul_id: uuid.UUID,
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
):
    calcul = _get_calcul_or_404(calcul_id, db)
    if calcul.statut == StatutCalculEnum.DEFINITIF:
        raise HTTPException(status_code=400, detail="Ce calcul est déjà validé")

    ancien_statut = calcul.statut.value
    calcul.statut = StatutCalculEnum.DEFINITIF
    calcul.valide_par_id = admin.id

    # Auto-transition dossier vers ENVOYE si le travail est terminé
    dossier = db.query(Dossier).filter(Dossier.id == calcul.dossier_id).first()
    if dossier and dossier.statut in (
        StatutDossierEnum.EN_MISE_EN_FORME,
        StatutDossierEnum.A_VALIDER,
        StatutDossierEnum.EN_CORRECTION,
        StatutDossierEnum.A_CORRIGER,
        StatutDossierEnum.EN_RETRANSCRIPTION,
    ):
        dossier.statut = StatutDossierEnum.ENVOYE

    log_action(
        db, TypeActionEnum.CALCUL_TARIFAIRE,
        dossier_id=calcul.dossier_id,
        utilisateur_id=admin.id,
        detail={
            "action": "validation_calcul",
            "calcul_id": str(calcul_id),
            "ancien_statut": ancien_statut,
            "montant_client_final": str(calcul.montant_client_final),
        },
    )
    db.commit()
    db.refresh(calcul)
    return calcul


@router.post("/calculs/{calcul_id}/ajuster", response_model=CalculOut)
def ajuster_calcul(
    calcul_id: uuid.UUID,
    payload: CalculAjustement,
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
):
    calcul = _get_calcul_or_404(calcul_id, db)
    if calcul.statut == StatutCalculEnum.DEFINITIF:
        raise HTTPException(status_code=400, detail="Impossible d'ajuster un calcul validé. Recalculez.")

    ancien_montant = calcul.montant_client_final
    calcul.ajustement_client = payload.ajustement_client
    calcul.motif_ajustement_client = payload.motif_ajustement_client
    calcul.montant_client_final = calcul.montant_client_brut + payload.ajustement_client
    calcul.marge_brute = calcul.montant_client_final - calcul.montant_prestataires_total
    calcul.statut = StatutCalculEnum.AJUSTE

    log_action(
        db, TypeActionEnum.AJUSTEMENT_TARIFAIRE,
        dossier_id=calcul.dossier_id,
        utilisateur_id=admin.id,
        detail={
            "action": "ajustement_calcul",
            "calcul_id": str(calcul_id),
            "montant_avant": str(ancien_montant),
            "ajustement": str(payload.ajustement_client),
            "montant_apres": str(calcul.montant_client_final),
            "motif": payload.motif_ajustement_client,
        },
    )
    db.commit()
    db.refresh(calcul)
    return calcul
