"""
Alertes périodiques : échéance proche (délai paramétré) et retard.
Idempotentes grâce aux clés de dédoublonnage : relancer la tâche ne duplique rien.
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.affectation import Affectation, StatutAffectationEnum
from app.models.dossier import Dossier
from app.services.notifications import notifier, compte_prestataire, internes

logger = logging.getLogger(__name__)

PRODUCTION_EN_ATTENTE_PRESTA = ("attribue", "en_cours", "correction_demandee")


def _aware(d):
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def executer_alertes(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    proches = retards = 0
    from app.services.delais import parametre
    heures = parametre(db, "alerte_echeance_heures")  # non paramétré : pas d'alerte « échéance proche »
    affs = db.query(Affectation).join(Dossier, Dossier.id == Affectation.dossier_id).filter(
        Affectation.statut.in_([StatutAffectationEnum.EN_ATTENTE, StatutAffectationEnum.EN_COURS]),
        Affectation.date_limite_rendu.isnot(None),
        Dossier.statut_production.in_(PRODUCTION_EN_ATTENTE_PRESTA),
        Dossier.supprime_le.is_(None),
    ).all()
    for aff in affs:
        d = db.query(Dossier).filter(Dossier.id == aff.dossier_id).first()
        ech = _aware(aff.date_limite_rendu)
        jour = ech.strftime("%d/%m/%Y")
        if ech < now:
            retards += 1
            notifier(db, compte_prestataire(db, aff.prestataire_id), "retard", f"Mission en retard : {d.reference}",
                     f"L'échéance du {jour} est dépassée. Merci de déposer votre PV au plus vite ou de prévenir la responsable.",
                     lien="/mes-missions", dossier_id=d.id, dedup_key=f"retard:{aff.id}:{jour}")
            notifier(db, internes(db, "dossiers.voir"), "retard", f"Retard : {d.reference}",
                     f"Échéance du retranscripteur dépassée ({jour}).", lien=f"/dossiers/{d.id}",
                     dossier_id=d.id, dedup_key=f"retard:{aff.id}:{jour}")
        elif heures and ech - now <= timedelta(hours=heures):
            proches += 1
            notifier(db, compte_prestataire(db, aff.prestataire_id), "echeance_proche",
                     f"Échéance proche : {d.reference}", f"À rendre au plus tard le {jour}.",
                     lien="/mes-missions", dossier_id=d.id, dedup_key=f"echeance:{aff.id}:{jour}")
    db.commit()
    return {"echeances_proches": proches, "retards": retards, "execute_le": now}


def _boucle():  # pragma: no cover — exécutée en production uniquement
    from app.db.session import SessionLocal
    from app.services import onedrive
    from app.services.graph_sync import run_sync
    dernier_sync = 0.0
    while True:
        db = SessionLocal()
        try:
            executer_alertes(db)
            intervalle = settings.GRAPH_SYNC_INTERVAL_MINUTES * 60
            if intervalle > 0 and onedrive.is_configured() and time.time() - dernier_sync >= intervalle:
                run_sync(db)
                dernier_sync = time.time()
        except Exception:
            logger.exception("[SCHEDULER] échec d'exécution")
            db.rollback()
        finally:
            db.close()
        time.sleep(max(settings.SCHEDULER_INTERVAL_MINUTES, 1) * 60)


def demarrer_planificateur() -> None:
    if settings.ENABLE_SCHEDULER:
        threading.Thread(target=_boucle, daemon=True, name="a2c-scheduler").start()
        logger.info("[SCHEDULER] démarré (toutes les %s min)", settings.SCHEDULER_INTERVAL_MINUTES)
