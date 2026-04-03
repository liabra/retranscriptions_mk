import uuid
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.dossier import Dossier
from app.models.affectation import Affectation, StatutAffectationEnum, RoleAffectationEnum
from app.models.pricing.calcul import CalculTarifaire, StatutCalculEnum
from app.models.user import User
from app.models.journal import TypeActionEnum
from app.schemas.calcul import CalculTrigger, CalculAjustement, CalculOut
from app.services.pricing.engine import PricingEngine
from app.services.journal import log_action

router = APIRouter()


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

    # Récupérer les affectations actives pour passer les IDs prestataires au moteur
    retrans_aff = db.query(Affectation).filter(
        Affectation.dossier_id == dossier_id,
        Affectation.type_role == RoleAffectationEnum.RETRANSCRIPTEUR,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).first()
    correct_aff = db.query(Affectation).filter(
        Affectation.dossier_id == dossier_id,
        Affectation.type_role == RoleAffectationEnum.CORRECTEUR,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).first()

    # Injecter les IDs prestataires dans les critères du dossier temporairement
    # Le moteur lit retranscripteur_id et correcteur_id via CriteresDossier
    # On patch directement en passant un wrapper
    original_criteres = dossier.criteres_tarif or {}

    # Déterminer la version
    existing_count = db.query(CalculTarifaire).filter(
        CalculTarifaire.dossier_id == dossier_id
    ).count()
    version = existing_count + 1

    # Stocker nb_pages sur le dossier si pas encore renseigné
    if not dossier.nombre_pages_final:
        dossier.nombre_pages_final = str(payload.nombre_pages)

    engine = PricingEngine(db)

    # Monkey-patch des IDs prestataires dans run_calcul
    # Le moteur crée CriteresDossier avec retranscripteur_id=None par défaut
    # On surcharge en créant la CriteresDossier nous-mêmes et en appelant les méthodes internes
    from app.services.pricing.engine import CriteresDossier
    from app.models.pricing.grille import TypeGrilleEnum

    criteres = CriteresDossier(
        type_instance=dossier.type_instance.value,
        urgence=dossier.est_urgent or original_criteres.get("urgence", False),
        sans_prise_de_note=original_criteres.get("sans_prise_de_note", False),
        prestation_speciale=original_criteres.get("prestation_speciale", False),
        type_prestation_speciale=original_criteres.get("type_prestation_speciale"),
        nombre_pages=payload.nombre_pages,
        client_id=dossier.client_id,
        retranscripteur_id=retrans_aff.prestataire_id if retrans_aff else None,
        correcteur_id=correct_aff.prestataire_id if correct_aff else None,
    )

    # Côté CLIENT
    grille_client = engine._get_active_grille(TypeGrilleEnum.CLIENT, criteres.client_id)
    grilles_client = [g for g in [grille_client] if g]
    if criteres.urgence:
        g_urg = engine._get_active_grille(TypeGrilleEnum.URGENCE)
        if g_urg:
            grilles_client.append(g_urg)
    if criteres.sans_prise_de_note:
        g_snp = engine._get_active_grille(TypeGrilleEnum.SNP)
        if g_snp:
            grilles_client.append(g_snp)
    if criteres.prestation_speciale:
        g_spe = engine._get_active_grille(TypeGrilleEnum.SPECIAL)
        if g_spe:
            grilles_client.append(g_spe)

    montant_client, lignes_client = engine._calcul_cote(grilles_client, criteres, "CLIENT")

    # Côté RETRANSCRIPTEUR
    grille_retrans = engine._get_active_grille(TypeGrilleEnum.RETRANSCRIPTEUR, criteres.retranscripteur_id)
    grilles_retrans = [g for g in [grille_retrans] if g]
    if criteres.urgence:
        g_urg_p = engine._get_active_grille(TypeGrilleEnum.URGENCE)
        if g_urg_p:
            grilles_retrans.append(g_urg_p)

    montant_retrans, lignes_retrans = engine._calcul_cote(grilles_retrans, criteres, "RETRANSCRIPTEUR")

    # Côté CORRECTEUR
    grille_correcteur = engine._get_active_grille(TypeGrilleEnum.CORRECTEUR, criteres.correcteur_id)
    grilles_correct = [g for g in [grille_correcteur] if g]
    montant_correct, lignes_correct = engine._calcul_cote(grilles_correct, criteres, "CORRECTEUR")

    if not grilles_client:
        raise HTTPException(
            status_code=422,
            detail="Aucune grille tarifaire CLIENT active trouvée. Configurez d'abord une grille.",
        )

    # Snapshot grilles
    grilles_snap = {}
    all_grilles = set(filter(None, grilles_client + grilles_retrans + grilles_correct))
    for g in all_grilles:
        grilles_snap[str(g.id)] = {"nom": g.nom, "version": g.version, "type": g.type.value}

    toutes_lignes = lignes_client + lignes_retrans + lignes_correct
    montant_presta_total = (montant_retrans + montant_correct).quantize(Decimal("0.01"))
    marge = (montant_client - montant_presta_total).quantize(Decimal("0.01"))

    calcul = CalculTarifaire(
        dossier_id=dossier_id,
        version_calcul=version,
        declenche_par_id=admin.id,
        nombre_pages=payload.nombre_pages,
        criteres_appliques=original_criteres,
        regles_appliquees=[
            {
                "regle_id": l.regle_id,
                "regle_libelle": l.regle_libelle,
                "grille_id": l.grille_id,
                "grille_version": l.grille_version,
                "condition_evaluee": l.condition_evaluee,
                "valeur_appliquee": l.valeur_appliquee,
                "impact_montant": str(l.impact_montant),
                "cible": l.cible,
                "ordre_application": l.ordre_application,
            }
            for l in toutes_lignes
        ],
        montant_client_brut=montant_client,
        ajustement_client=Decimal("0.00"),
        montant_client_final=montant_client,
        montant_retranscripteur=montant_retrans,
        montant_correcteur=montant_correct,
        montant_prestataires_total=montant_presta_total,
        marge_brute=marge,
        grilles_version_snap=grilles_snap,
        statut=StatutCalculEnum.ESTIMATIF if version == 1 else StatutCalculEnum.DEFINITIF,
    )

    db.add(calcul)
    db.flush()
    dossier.calcul_tarifaire_id = calcul.id

    log_action(
        db, TypeActionEnum.CALCUL_TARIFAIRE,
        dossier_id=dossier_id,
        utilisateur_id=admin.id,
        detail={
            "action": "calcul_tarifaire",
            "calcul_id": str(calcul.id),
            "version": version,
            "nombre_pages": str(payload.nombre_pages),
            "montant_client_final": str(calcul.montant_client_final),
        },
    )
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
