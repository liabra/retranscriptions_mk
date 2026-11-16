"""Tableau de bord : compteurs calculés côté serveur sur les données réelles."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func

from app.api.v1.common import AFF_ACTIVES
from app.core.deps import DbDep, require_internal
from app.core.permissions import has_permission
from app.models.affectation import Affectation
from app.models.dossier import Dossier
from app.models.facture import FactureClient, StatutPaiementEnum
from app.models.paiement import PaiementPrestataire, StatutPaiementPrestaEnum
from app.models.refonte import AudioSource, Encaissement
from app.models.user import User

router = APIRouter()


@router.get("/dashboard")
def resume(db: DbDep, user: User = Depends(require_internal)):
    vivants = db.query(Dossier).filter(Dossier.supprime_le.is_(None))

    def prod(*statuts):
        return vivants.filter(Dossier.statut_production.in_(statuts)).count()

    today = date.today()
    now = datetime.now(timezone.utc)
    retard_dossier = vivants.filter(
        Dossier.statut_production.notin_(["valide", "archive", "bloque"]),
        Dossier.date_limite < today,
    ).with_entities(Dossier.id)
    retard_aff = db.query(Affectation.dossier_id).join(Dossier, Dossier.id == Affectation.dossier_id).filter(
        Affectation.statut.in_(AFF_ACTIVES), Affectation.date_limite_rendu < now,
        Dossier.statut_production.in_(["attribue", "en_cours", "correction_demandee"]),
        Dossier.supprime_le.is_(None),
    )
    retards = len({r[0] for r in retard_dossier.all()} | {r[0] for r in retard_aff.all()})

    production = {}
    if has_permission(user, "dossiers.voir"):
        production = {
            "nouveaux_audios": db.query(AudioSource).filter(AudioSource.statut == "a_traiter").count()
            if has_permission(user, "audios.gerer") else None,
            "a_qualifier": prod("a_qualifier"),
            "a_attribuer": prod("a_attribuer"),
            "en_cours": prod("attribue", "en_cours"),
            "en_retard": retards,
            "pv_recus": prod("livre"),
            "a_relire": prod("a_relire"),
            "corrections_demandees": prod("correction_demandee"),
            "a_controler": prod("a_controler"),
            "valides": prod("valide"),
            "bloques": prod("bloque"),
        }

    finance = None
    if has_permission(user, "finance.voir"):
        actives = db.query(FactureClient).filter(FactureClient.annulee_le.is_(None))
        attente = actives.filter(FactureClient.statut_paiement != StatutPaiementEnum.SOLDEE)
        debut_mois = today.replace(day=1)
        paiements_a = db.query(PaiementPrestataire).filter(PaiementPrestataire.statut != StatutPaiementPrestaEnum.PAYE)
        paiements_ok = db.query(PaiementPrestataire).filter(PaiementPrestataire.statut == StatutPaiementPrestaEnum.PAYE)
        finance = {
            "factures_a_etablir": vivants.filter(Dossier.statut_facturation == "a_etablir").count(),
            "encaissements_attendus": attente.count(),
            "montant_attendu": float(attente.with_entities(
                func.coalesce(func.sum(FactureClient.montant_ttc - FactureClient.montant_encaisse), 0)).scalar() or 0),
            "encaissements_recus_mois": db.query(Encaissement).filter(
                Encaissement.date_encaissement >= debut_mois).count(),
            "montant_encaisse_mois": float(db.query(func.coalesce(func.sum(Encaissement.montant), 0))
                                           .filter(Encaissement.date_encaissement >= debut_mois).scalar() or 0),
            "paiements_a_effectuer": paiements_a.count(),
            "montant_a_payer": float(paiements_a.with_entities(
                func.coalesce(func.sum(PaiementPrestataire.montant_final), 0)).scalar() or 0),
            "paiements_effectues": paiements_ok.count(),
        }
    return {"production": production, "finance": finance, "genere_le": now}
