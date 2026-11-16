"""
Service de calcul tarifaire.

- Aucun montant codé en dur : tout provient des grilles administrables (services/tarifs.py).
- Grilles choisies à la date de réception de l'audio (non-rétroactivité).
- Chaque calcul conserve une copie intégrale des grilles et règles appliquées.
- Tout calcul est créé « estimatif » et doit être validé par une personne habilitée.
"""
import uuid
from decimal import Decimal

from app.models.affectation import Affectation, RoleAffectationEnum, StatutAffectationEnum
from app.models.dossier import Dossier
from app.models.journal import TypeActionEnum
from app.models.pricing.calcul import CalculTarifaire, StatutCalculEnum
from app.services import tarifs
from app.services.journal import log_action


def date_reference(dossier: Dossier):
    """Date d'application des tarifs : réception de l'audio (à défaut, création du dossier)."""
    ref = dossier.date_reception_audio or dossier.created_at
    return ref.date() if hasattr(ref, "date") else ref


def run_calcul(dossier: Dossier, nombre_pages: Decimal, triggered_by_id: uuid.UUID, db) -> CalculTarifaire:
    """Calcule et enregistre une nouvelle version de calcul (non commitée)."""
    def aff(role):
        return db.query(Affectation).filter(
            Affectation.dossier_id == dossier.id, Affectation.type_role == role,
            Affectation.statut != StatutAffectationEnum.REJETE,
        ).order_by(Affectation.date_attribution.desc()).first()

    retrans_aff, correct_aff = aff(RoleAffectationEnum.RETRANSCRIPTEUR), aff(RoleAffectationEnum.CORRECTEUR)
    criteres = dossier.criteres_tarif or {}
    ref = date_reference(dossier)
    res = tarifs.calculer(db, tarifs.Contexte(
        type_instance=dossier.type_instance.value, nombre_pages=nombre_pages, date_reference=ref,
        client_id=dossier.client_id,
        retranscripteur_id=retrans_aff.prestataire_id if retrans_aff else None,
        correcteur_id=correct_aff.prestataire_id if correct_aff else None,
        criteres=criteres, est_urgent=dossier.est_urgent, date_limite=dossier.date_limite,
    ))
    version = db.query(CalculTarifaire).filter(CalculTarifaire.dossier_id == dossier.id).count() + 1
    if not dossier.nombre_pages_final:
        dossier.nombre_pages_final = nombre_pages

    montant_presta_total = (res.montant_retranscripteur + res.montant_correcteur).quantize(Decimal("0.01"))
    calcul = CalculTarifaire(
        dossier_id=dossier.id,
        version_calcul=version,
        declenche_par_id=triggered_by_id,
        nombre_pages=nombre_pages,
        criteres_appliques={**criteres, "_tarification": {
            "date_reference": ref.isoformat(), "majorations_appliquees": res.majorations,
            "dossier_signale_urgent": dossier.est_urgent,
        }},
        regles_appliquees=[{
            "regle_id": l.regle_id, "regle_libelle": l.regle_libelle, "grille_id": l.grille_id,
            "grille_version": l.grille_version, "condition_evaluee": l.condition_evaluee,
            "valeur_appliquee": l.valeur_appliquee, "impact_montant": str(l.impact_montant),
            "cible": l.cible, "ordre_application": l.ordre_application,
        } for l in res.lignes],
        montant_client_brut=res.montant_client,
        ajustement_client=Decimal("0.00"),
        montant_client_final=res.montant_client,
        montant_retranscripteur=res.montant_retranscripteur,
        montant_correcteur=res.montant_correcteur,
        montant_prestataires_total=montant_presta_total,
        marge_brute=(res.montant_client - montant_presta_total).quantize(Decimal("0.01")),
        # Copie intégrale des paramètres : le calcul reste lisible même si la grille évolue ensuite
        grilles_version_snap={str(g.id): tarifs.snapshot(db, g) for g in res.grilles},
        statut=StatutCalculEnum.ESTIMATIF,
    )
    db.add(calcul)
    db.flush()
    dossier.calcul_tarifaire_id = calcul.id
    log_action(db, TypeActionEnum.CALCUL_TARIFAIRE, dossier_id=dossier.id, utilisateur_id=triggered_by_id, detail={
        "action": "calcul_tarifaire", "version": version, "nombre_pages": str(nombre_pages),
        "montant_client_final": str(res.montant_client), "montant_retranscripteur": str(res.montant_retranscripteur),
        "date_reference_tarifs": ref.isoformat(), "grilles": [f"{g.nom} v{g.version}" for g in res.grilles],
    })
    return calcul
