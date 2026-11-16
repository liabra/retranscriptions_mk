"""
Délais de réalisation et paramètres métier — administrables, aucune valeur métier dans le code.

Échéance prévisionnelle du PV final = date de réception de l'audio + délai de la première règle
applicable (priorité croissante). Si aucun paramètre n'est défini, rien n'est déduit :
l'échéance reste à saisir et aucune alerte automatique n'est émise.
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.refonte import Parametre, RegleDelai

PARAMETRES = {
    "seuil_urgence_jours": "Dossier signalé urgent si l'échéance client est à moins de N jours",
    "alerte_echeance_heures": "Alerte « échéance proche » N heures avant l'échéance du retranscripteur",
    "marge_relecture_jours": "Rendu attendu du retranscripteur N jours avant l'échéance client (temps de relecture)",
}


def parametre(db: Session, cle: str) -> Optional[int]:
    p = db.query(Parametre).filter(Parametre.cle == cle).first()
    if not p or not p.valeur or p.valeur.get("valeur") is None:
        return None
    return int(p.valeur["valeur"])


def ajouter_jours(depart: date, jours: int, type_jours: str) -> date:
    if type_jours != "ouvres":
        return depart + timedelta(days=jours)
    d, restants = depart, jours
    while restants > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:  # lundi–vendredi (jours fériés non pris en compte)
            restants -= 1
    return d


def regle_applicable(db: Session, type_instance: Optional[str], duree_minutes: Optional[int],
                     urgence: bool, criteres: Optional[dict]) -> Optional[RegleDelai]:
    crit = criteres or {}
    for r in db.query(RegleDelai).filter(RegleDelai.actif == True).order_by(RegleDelai.priorite, RegleDelai.libelle).all():  # noqa: E712
        if r.type_instance and r.type_instance != type_instance:
            continue
        if r.duree_min_minutes is not None and (duree_minutes is None or duree_minutes <= r.duree_min_minutes):
            continue
        if r.duree_max_minutes is not None and (duree_minutes is None or duree_minutes > r.duree_max_minutes):
            continue
        if r.urgence is not None and bool(urgence) != r.urgence:
            continue
        if r.prestation == "snp" and not crit.get("sans_prise_de_note"):
            continue
        if r.prestation == "special" and not crit.get("prestation_speciale"):
            continue
        return r
    return None


def echeance_prevue(db: Session, date_reception: datetime, type_instance: Optional[str],
                    duree_minutes: Optional[int], criteres: Optional[dict]) -> Tuple[Optional[date], Optional[dict]]:
    crit = criteres or {}
    r = regle_applicable(db, type_instance, duree_minutes, bool(crit.get("urgence")), crit)
    if not r:
        return None, None
    reception = date_reception.date() if isinstance(date_reception, datetime) else date_reception
    echeance = ajouter_jours(reception, r.delai_jours, r.type_jours)
    return echeance, {
        "regle_id": str(r.id), "regle": r.libelle, "delai_jours": r.delai_jours, "type_jours": r.type_jours,
        "date_reception": reception.isoformat(), "calculee_le": datetime.now(timezone.utc).isoformat(),
    }


def appliquer_echeance(db: Session, dossier) -> bool:
    """Recalcule l'échéance d'un dossier en mode « calculée ». Retourne True si une échéance a été trouvée."""
    ech, detail = echeance_prevue(db, dossier.date_reception_audio, dossier.type_instance.value,
                                  dossier.duree_audio_minutes, dossier.criteres_tarif)
    dossier.echeance_mode = "calculee"
    dossier.echeance_detail = detail or {"regle": None, "motif": "Aucune règle de délai applicable"}
    dossier.date_limite = ech
    return ech is not None


def est_urgent(db: Session, date_limite: Optional[date]) -> bool:
    """Dossier signalé urgent si l'échéance est à moins du seuil paramétré (aucun seuil = jamais)."""
    seuil = parametre(db, "seuil_urgence_jours")
    if seuil is None or not date_limite:
        return False
    return (date_limite - datetime.now(timezone.utc).date()).days < seuil


def echeance_retranscripteur(db: Session, date_limite: Optional[date]) -> Optional[datetime]:
    """Rendu attendu du retranscripteur : échéance client moins la marge de relecture paramétrée."""
    if not date_limite:
        return None
    marge = parametre(db, "marge_relecture_jours") or 0
    return datetime.combine(date_limite - timedelta(days=marge), time(18, 0), tzinfo=timezone.utc)


# ── Cycle de vie de l'échéance client ─────────────────────────────────────────
# Prévisionnelle (calculée) → recalculable tant que le dossier n'est pas attribué → figée à la
# première attribution. Seule une modification manuelle autorisée peut ensuite la changer.
AVANT_ATTRIBUTION = ("a_qualifier", "a_attribuer")


def recalculable(dossier) -> bool:
    return (dossier.echeance_mode == "calculee" and dossier.echeance_figee_le is None
            and dossier.statut_production in AVANT_ATTRIBUTION)


def tracer(db: Session, dossier, user_id, action: str, ancienne: Optional[date], mode_avant: Optional[str],
           motif: Optional[str] = None) -> None:
    """Historique : ancienne et nouvelle valeur ; l'auteur et la date sont ceux de l'entrée du journal."""
    from app.models.journal import TypeActionEnum
    from app.services.journal import log_action
    if ancienne == dossier.date_limite and mode_avant == dossier.echeance_mode and action != "echeance_figee":
        return
    log_action(db, TypeActionEnum.NOTE, dossier_id=dossier.id, utilisateur_id=user_id, detail={
        "action": action,
        "ancien": ancienne.isoformat() if ancienne else None,
        "nouveau": dossier.date_limite.isoformat() if dossier.date_limite else None,
        "mode_avant": mode_avant, "mode_apres": dossier.echeance_mode,
        "regle": (dossier.echeance_detail or {}).get("regle") if dossier.echeance_mode == "calculee" else None,
        **({"motif": motif} if motif else {}),
    })


def figer(db: Session, dossier, user_id) -> None:
    if dossier.echeance_figee_le is None:
        dossier.echeance_figee_le = datetime.now(timezone.utc)
        tracer(db, dossier, user_id, "echeance_figee", dossier.date_limite, dossier.echeance_mode,
               "attribution du dossier")


def recalculer_non_attribues(db: Session, user_id) -> int:
    """Après un changement de règles : met à jour les échéances encore prévisionnelles."""
    from app.models.dossier import Dossier
    n = 0
    for d in db.query(Dossier).filter(
        Dossier.supprime_le.is_(None), Dossier.echeance_mode == "calculee", Dossier.echeance_figee_le.is_(None),
        Dossier.statut_production.in_(AVANT_ATTRIBUTION),
    ).all():
        ancienne, mode = d.date_limite, d.echeance_mode
        appliquer_echeance(db, d)
        if d.date_limite != ancienne:
            if not d.urgence_forcee:
                d.est_urgent = est_urgent(db, d.date_limite) or bool((d.criteres_tarif or {}).get("urgence"))
            tracer(db, d, user_id, "echeance_recalculee", ancienne, mode, "modification des règles de délai")
            n += 1
    return n
