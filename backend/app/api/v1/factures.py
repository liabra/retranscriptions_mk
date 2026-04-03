import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.dossier import Dossier
from app.models.facture import FactureClient, StatutPaiementEnum
from app.models.pricing.calcul import CalculTarifaire
from app.models.user import User
from app.models.journal import TypeActionEnum
from app.schemas.facture import FactureGenerate, FacturePaiementUpdate, FactureOut
from app.services.journal import log_action

router = APIRouter()


def _get_dossier_or_404(dossier_id: uuid.UUID, db) -> Dossier:
    d = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return d


def _generate_numero_facture(db) -> str:
    year = datetime.now(timezone.utc).year
    count = (
        db.query(FactureClient)
        .filter(FactureClient.numero_facture.like(f"FAC-{year}-%"))
        .count()
    )
    return f"FAC-{year}-{count + 1:04d}"


@router.post("/dossiers/{dossier_id}/generer-facture", response_model=FactureOut, status_code=201)
def generer_facture(
    dossier_id: uuid.UUID,
    payload: FactureGenerate,
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
):
    dossier = _get_dossier_or_404(dossier_id, db)

    existing = db.query(FactureClient).filter(FactureClient.dossier_id == dossier_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Une facture existe déjà pour ce dossier")

    if not dossier.calcul_tarifaire_id:
        raise HTTPException(status_code=400, detail="Aucun calcul tarifaire disponible. Calculez d'abord.")

    calcul = db.query(CalculTarifaire).filter(CalculTarifaire.id == dossier.calcul_tarifaire_id).first()
    if not calcul:
        raise HTTPException(status_code=404, detail="Calcul tarifaire introuvable")

    payeur_id = dossier.payeur_id or dossier.client_id
    montant_ht = calcul.montant_client_final
    taux_tva = Decimal("0.00")
    montant_tva = Decimal("0.00")

    if payload.tva_applicable:
        taux_tva = payload.taux_tva
        montant_tva = (montant_ht * taux_tva / Decimal("100")).quantize(Decimal("0.01"))

    montant_ttc = montant_ht + montant_tva

    facture = FactureClient(
        numero_facture=_generate_numero_facture(db),
        dossier_id=dossier_id,
        payeur_id=payeur_id,
        calcul_tarifaire_id=calcul.id,
        montant_ht=montant_ht,
        tva_applicable=payload.tva_applicable,
        taux_tva=taux_tva,
        montant_tva=montant_tva,
        montant_ttc=montant_ttc,
        date_emission=date.today(),
        date_echeance=payload.date_echeance,
        statut_paiement=StatutPaiementEnum.NON_PAYEE,
    )
    db.add(facture)
    db.flush()

    log_action(
        db, TypeActionEnum.PAIEMENT,
        dossier_id=dossier_id,
        utilisateur_id=admin.id,
        detail={
            "action": "generation_facture",
            "numero_facture": facture.numero_facture,
            "montant_ttc": str(montant_ttc),
        },
    )
    db.commit()
    db.refresh(facture)
    return facture


@router.get("/dossiers/{dossier_id}/facture", response_model=FactureOut)
def get_facture_dossier(dossier_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    _get_dossier_or_404(dossier_id, db)
    facture = db.query(FactureClient).filter(FactureClient.dossier_id == dossier_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Aucune facture pour ce dossier")
    return facture


@router.get("/factures/{facture_id}", response_model=FactureOut)
def get_facture(facture_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    facture = db.query(FactureClient).filter(FactureClient.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return facture


@router.patch("/factures/{facture_id}/paiement", response_model=FactureOut)
def update_facture_paiement(
    facture_id: uuid.UUID,
    payload: FacturePaiementUpdate,
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
):
    facture = db.query(FactureClient).filter(FactureClient.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    try:
        facture.statut_paiement = StatutPaiementEnum(payload.statut_paiement)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Statut invalide: {payload.statut_paiement}")

    log_action(
        db, TypeActionEnum.PAIEMENT,
        dossier_id=facture.dossier_id,
        utilisateur_id=admin.id,
        detail={
            "action": "update_statut_facture",
            "facture_id": str(facture_id),
            "statut": payload.statut_paiement,
        },
    )
    db.commit()
    db.refresh(facture)
    return facture
