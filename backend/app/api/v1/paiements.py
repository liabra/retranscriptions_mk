import uuid
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.dossier import Dossier, StatutDossierEnum
from app.models.affectation import Affectation, StatutAffectationEnum, RoleAffectationEnum
from app.models.paiement import PaiementPrestataire, StatutPaiementPrestaEnum, RolePayeEnum
from app.models.pricing.calcul import CalculTarifaire
from app.models.user import User, RoleEnum
from app.models.journal import TypeActionEnum
from app.schemas.paiement_presta import PaiementPrestaUpdate, PaiementPrestaOut
from app.services.journal import log_action

router = APIRouter()


def _get_dossier_or_404(dossier_id: uuid.UUID, db) -> Dossier:
    d = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return d


@router.post(
    "/dossiers/{dossier_id}/generer-paiements-prestataires",
    response_model=List[PaiementPrestaOut],
    status_code=201,
)
def generer_paiements_prestataires(
    dossier_id: uuid.UUID,
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
):
    dossier = _get_dossier_or_404(dossier_id, db)

    if not dossier.calcul_tarifaire_id:
        raise HTTPException(status_code=400, detail="Aucun calcul tarifaire disponible")

    calcul = db.query(CalculTarifaire).filter(CalculTarifaire.id == dossier.calcul_tarifaire_id).first()
    if not calcul:
        raise HTTPException(status_code=404, detail="Calcul tarifaire introuvable")

    if not dossier.nombre_pages_final:
        raise HTTPException(status_code=400, detail="Nombre de pages final non renseigné")

    existing = db.query(PaiementPrestataire).filter(
        PaiementPrestataire.dossier_id == dossier_id
    ).count()
    if existing > 0:
        raise HTTPException(status_code=400, detail="Des paiements existent déjà pour ce dossier")

    affectations = db.query(Affectation).filter(
        Affectation.dossier_id == dossier_id,
        Affectation.statut.in_([
            StatutAffectationEnum.LIVRE,
            StatutAffectationEnum.VALIDE,
            StatutAffectationEnum.EN_COURS,
        ]),
    ).all()

    if not affectations:
        raise HTTPException(
            status_code=400,
            detail="Aucune affectation active/livrée pour ce dossier",
        )

    nombre_pages = Decimal(str(dossier.nombre_pages_final))
    created = []

    for aff in affectations:
        if aff.type_role == RoleAffectationEnum.RETRANSCRIPTEUR:
            montant_brut = calcul.montant_retranscripteur
            role = RolePayeEnum.RETRANSCRIPTEUR
        else:
            montant_brut = calcul.montant_correcteur
            role = RolePayeEnum.CORRECTEUR

        paiement = PaiementPrestataire(
            affectation_id=aff.id,
            dossier_id=dossier_id,
            prestataire_id=aff.prestataire_id,
            role_paye=role,
            nombre_pages=nombre_pages,
            detail_calcul={
                "calcul_id": str(calcul.id),
                "version_calcul": calcul.version_calcul,
                "montant_client_final": str(calcul.montant_client_final),
            },
            montant_brut=montant_brut,
            ajustement_manuel=Decimal("0.00"),
            montant_final=montant_brut,
            statut=StatutPaiementPrestaEnum.A_PAYER,
        )
        db.add(paiement)
        created.append(paiement)

    db.flush()
    log_action(
        db, TypeActionEnum.PAIEMENT,
        dossier_id=dossier_id,
        utilisateur_id=admin.id,
        detail={"action": "generation_paiements_presta", "nb_paiements": len(created)},
    )
    db.commit()
    for p in created:
        db.refresh(p)
    return created


@router.get("/dossiers/{dossier_id}/paiements-prestataires", response_model=List[PaiementPrestaOut])
def list_paiements_dossier(dossier_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    _get_dossier_or_404(dossier_id, db)
    return db.query(PaiementPrestataire).filter(
        PaiementPrestataire.dossier_id == dossier_id
    ).all()


@router.patch("/paiements-prestataires/{paiement_id}", response_model=PaiementPrestaOut)
def update_paiement(
    paiement_id: uuid.UUID,
    payload: PaiementPrestaUpdate,
    db: DbDep,
    current_user: CurrentUser,
):
    if current_user.role not in (
        RoleEnum.ADMINISTRATRICE, RoleEnum.COORDINATRICE, RoleEnum.COMPTABILITE
    ):
        raise HTTPException(status_code=403, detail="Accès refusé")

    paiement = db.query(PaiementPrestataire).filter(PaiementPrestataire.id == paiement_id).first()
    if not paiement:
        raise HTTPException(status_code=404, detail="Paiement introuvable")

    changes = payload.model_dump(exclude_unset=True)
    if "statut" in changes:
        try:
            changes["statut"] = StatutPaiementPrestaEnum(changes["statut"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Statut invalide: {changes['statut']}")

    for field, value in changes.items():
        setattr(paiement, field, value)

    if payload.ajustement_manuel is not None:
        paiement.montant_final = paiement.montant_brut + payload.ajustement_manuel

    # Auto-transition dossier → PRESTATAIRES_PAYES si tous les paiements sont payés
    if getattr(payload, "statut", None) == "paye":
        tous_paiements = db.query(PaiementPrestataire).filter(
            PaiementPrestataire.dossier_id == paiement.dossier_id
        ).all()
        if tous_paiements and all(p.statut == StatutPaiementPrestaEnum.PAYE for p in tous_paiements):
            dossier = db.query(Dossier).filter(Dossier.id == paiement.dossier_id).first()
            if dossier and dossier.statut == StatutDossierEnum.PAYE_ENTRANT:
                dossier.statut = StatutDossierEnum.PRESTATAIRES_PAYES

    log_action(
        db, TypeActionEnum.PAIEMENT,
        dossier_id=paiement.dossier_id,
        utilisateur_id=current_user.id,
        detail={
            "action": "update_paiement_presta",
            "paiement_id": str(paiement_id),
            "changements": payload.model_dump(exclude_unset=True, mode="json"),
        },
    )
    db.commit()
    db.refresh(paiement)
    return paiement
