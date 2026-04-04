"""
Service de calcul tarifaire — logique extraite pour réutilisation
(endpoint manuel + auto-calcul déclenché par livraison).
"""
import uuid
from decimal import Decimal

from app.models.affectation import Affectation, RoleAffectationEnum, StatutAffectationEnum
from app.models.dossier import Dossier
from app.models.journal import TypeActionEnum
from app.models.pricing.calcul import CalculTarifaire, StatutCalculEnum
from app.models.pricing.grille import TypeGrilleEnum
from app.services.journal import log_action
from app.services.pricing.engine import CriteresDossier, PricingEngine


def _forfait_a2c(nombre_pages: Decimal) -> Decimal:
    p = float(nombre_pages)
    if p <= 0:   return Decimal("0.00")
    if p <= 9:   return Decimal("50.00")
    if p <= 20:  return Decimal("100.00")
    if p <= 30:  return Decimal("150.00")
    if p <= 40:  return Decimal("200.00")
    if p <= 50:  return Decimal("250.00")
    if p <= 60:  return Decimal("300.00")
    if p <= 70:  return Decimal("350.00")
    if p <= 80:  return Decimal("400.00")
    if p <= 90:  return Decimal("450.00")
    if p <= 100: return Decimal("500.00")
    return (Decimal(str(p)) * Decimal("5.00")).quantize(Decimal("0.01"))


def run_calcul(dossier: Dossier, nombre_pages: Decimal,
               triggered_by_id: uuid.UUID, db) -> CalculTarifaire:
    """
    Exécute le calcul tarifaire complet pour un dossier.
    Auto-valide si le montant correspond exactement au forfait A2C standard.
    Retourne le CalculTarifaire créé (non commité — appelant doit commit).
    """
    retrans_aff = db.query(Affectation).filter(
        Affectation.dossier_id == dossier.id,
        Affectation.type_role == RoleAffectationEnum.RETRANSCRIPTEUR,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).first()
    correct_aff = db.query(Affectation).filter(
        Affectation.dossier_id == dossier.id,
        Affectation.type_role == RoleAffectationEnum.CORRECTEUR,
        Affectation.statut != StatutAffectationEnum.REJETE,
    ).first()

    original_criteres = dossier.criteres_tarif or {}
    existing_count = db.query(CalculTarifaire).filter(
        CalculTarifaire.dossier_id == dossier.id
    ).count()
    version = existing_count + 1

    if not dossier.nombre_pages_final:
        dossier.nombre_pages_final = str(nombre_pages)

    engine = PricingEngine(db)
    criteres = CriteresDossier(
        type_instance=dossier.type_instance.value,
        urgence=dossier.est_urgent or original_criteres.get("urgence", False),
        sans_prise_de_note=original_criteres.get("sans_prise_de_note", False),
        prestation_speciale=original_criteres.get("prestation_speciale", False),
        type_prestation_speciale=original_criteres.get("type_prestation_speciale"),
        nombre_pages=nombre_pages,
        client_id=dossier.client_id,
        retranscripteur_id=retrans_aff.prestataire_id if retrans_aff else None,
        correcteur_id=correct_aff.prestataire_id if correct_aff else None,
    )

    # Côté CLIENT
    grille_client = engine._get_active_grille(TypeGrilleEnum.CLIENT, criteres.client_id)
    grilles_client = [g for g in [grille_client] if g]
    if criteres.urgence:
        g = engine._get_active_grille(TypeGrilleEnum.URGENCE)
        if g: grilles_client.append(g)
    if criteres.sans_prise_de_note:
        g = engine._get_active_grille(TypeGrilleEnum.SNP)
        if g: grilles_client.append(g)
    if criteres.prestation_speciale:
        g = engine._get_active_grille(TypeGrilleEnum.SPECIAL)
        if g: grilles_client.append(g)

    if grilles_client:
        montant_client, lignes_client = engine._calcul_cote(grilles_client, criteres, "CLIENT")
        if montant_client == Decimal("0.00"):
            montant_client = _forfait_a2c(criteres.nombre_pages)
            lignes_client = []
    else:
        montant_client = _forfait_a2c(criteres.nombre_pages)
        lignes_client = []

    # Côté RETRANSCRIPTEUR
    grille_retrans = engine._get_active_grille(TypeGrilleEnum.RETRANSCRIPTEUR, criteres.retranscripteur_id)
    grilles_retrans = [g for g in [grille_retrans] if g]
    if criteres.urgence:
        g = engine._get_active_grille(TypeGrilleEnum.URGENCE)
        if g: grilles_retrans.append(g)
    montant_retrans, lignes_retrans = engine._calcul_cote(grilles_retrans, criteres, "RETRANSCRIPTEUR")

    # Côté CORRECTEUR
    grille_correcteur = engine._get_active_grille(TypeGrilleEnum.CORRECTEUR, criteres.correcteur_id)
    grilles_correct = [g for g in [grille_correcteur] if g]
    montant_correct, lignes_correct = engine._calcul_cote(grilles_correct, criteres, "CORRECTEUR")

    grilles_snap = {}
    for g in set(filter(None, grilles_client + grilles_retrans + grilles_correct)):
        grilles_snap[str(g.id)] = {"nom": g.nom, "version": g.version, "type": g.type.value}

    toutes_lignes = lignes_client + lignes_retrans + lignes_correct
    montant_presta_total = (montant_retrans + montant_correct).quantize(Decimal("0.01"))
    marge = (montant_client - montant_presta_total).quantize(Decimal("0.01"))

    # Auto-validation si le montant client = forfait A2C exact (pas d'ajustement nécessaire)
    auto_valide = (montant_client == _forfait_a2c(nombre_pages))
    statut = StatutCalculEnum.DEFINITIF if auto_valide else StatutCalculEnum.ESTIMATIF

    calcul = CalculTarifaire(
        dossier_id=dossier.id,
        version_calcul=version,
        declenche_par_id=triggered_by_id,
        nombre_pages=nombre_pages,
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
        statut=statut,
    )
    db.add(calcul)
    db.flush()
    dossier.calcul_tarifaire_id = calcul.id

    log_action(
        db, TypeActionEnum.CALCUL_TARIFAIRE,
        dossier_id=dossier.id,
        utilisateur_id=triggered_by_id,
        detail={
            "action": "auto_calcul" if auto_valide else "calcul_tarifaire",
            "version": version,
            "nombre_pages": str(nombre_pages),
            "montant_client_final": str(montant_client),
            "auto_valide": auto_valide,
        },
    )
    return calcul
