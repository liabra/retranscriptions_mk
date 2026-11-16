"""
Attribution assistée — indicateurs de performance et suggestions.

Principes :
- aucune attribution automatique : ce module classe, la responsable choisit ;
- aucun indicateur inventé : chaque indicateur vaut None tant qu'il n'existe pas de donnée ;
- en dessous de SEUIL_FIABLE missions terminées, l'historique est signalé comme insuffisant
  et n'entre pas dans le score ;
- résultats réservés aux responsables internes (jamais exposés aux prestataires).
"""
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.affectation import Affectation, StatutAffectationEnum, RoleAffectationEnum
from app.models.dossier import Dossier
from app.models.prestataire import Prestataire, RolePrestaEnum
from app.models.refonte import Livraison, DemandeCorrection

SEUIL_FIABLE = 3
SEUIL_BONNE = 10
ACTIVES = (StatutAffectationEnum.EN_ATTENTE, StatutAffectationEnum.EN_COURS, StatutAffectationEnum.LIVRE)


def _aware(d: Optional[datetime]) -> Optional[datetime]:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


@dataclass
class Performance:
    prestataire_id: str
    nom: str
    disponible: bool
    missions_terminees: int = 0
    missions_retirees: int = 0
    charge_actuelle: int = 0
    minutes_en_cours: int = 0
    respect_delais: Optional[float] = None      # part livrée à temps (0-1)
    delai_moyen_jours: Optional[float] = None
    rapidite_min_par_jour: Optional[float] = None
    qualite: Optional[float] = None             # 1 - corrections / livraisons
    conformite_docx: Optional[float] = None     # part des dépôts conformes
    fiabilite: Optional[float] = None           # 1 - retraits / attributions
    regularite: Optional[float] = None          # 1 - coefficient de variation des délais
    specialites_declarees: List[str] = field(default_factory=list)
    missions_par_instance: Dict[str, int] = field(default_factory=dict)
    fiabilite_donnees: str = "insuffisante"     # insuffisante | limitee | bonne

    def dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = round(v, 3)
        return d


def performances(db: Session, prestataire_ids: Optional[List] = None) -> Dict[str, Performance]:
    q = db.query(Prestataire).filter(Prestataire.actif == True)  # noqa: E712
    q = q.filter(Prestataire.role != RolePrestaEnum.CORRECTEUR)
    if prestataire_ids:
        q = q.filter(Prestataire.id.in_(prestataire_ids))
    prestas = q.all()
    result: Dict[str, Performance] = {}
    for p in prestas:
        perf = Performance(prestataire_id=str(p.id), nom=p.nom, disponible=p.disponible,
                           specialites_declarees=list(p.specialites or []))
        affs = db.query(Affectation).filter(
            Affectation.prestataire_id == p.id,
            Affectation.type_role == RoleAffectationEnum.RETRANSCRIPTEUR,
        ).all()
        delais, a_temps, avec_echeance, vitesses = [], 0, 0, []
        nb_livraisons = nb_conformes = nb_corrections = 0
        for a in affs:
            dossier = db.query(Dossier).filter(Dossier.id == a.dossier_id).first()
            if a.statut == StatutAffectationEnum.REJETE:
                perf.missions_retirees += 1
                continue
            if a.statut in ACTIVES and dossier and dossier.statut_production not in ("valide", "archive"):
                perf.charge_actuelle += 1
                perf.minutes_en_cours += dossier.duree_audio_minutes or 0
            livs = db.query(Livraison).filter(
                Livraison.affectation_id == a.id, Livraison.type_depot == "depot_prestataire"
            ).order_by(Livraison.version).all()
            nb_livraisons += len(livs)
            nb_conformes += sum(1 for l in livs if l.statut_controle in ("conforme", "avertissements"))
            nb_corrections += db.query(DemandeCorrection).filter(DemandeCorrection.affectation_id == a.id).count()
            if a.statut != StatutAffectationEnum.VALIDE:
                continue
            perf.missions_terminees += 1
            if dossier:
                ti = dossier.type_instance.value
                perf.missions_par_instance[ti] = perf.missions_par_instance.get(ti, 0) + 1
            if livs:
                premier = _aware(livs[0].depose_le)
                debut = _aware(a.date_attribution)
                if premier and debut:
                    jours = max((premier - debut).total_seconds() / 86400, 0.1)
                    delais.append(jours)
                    if dossier and dossier.duree_audio_minutes:
                        vitesses.append(dossier.duree_audio_minutes / jours)
                limite = _aware(a.date_limite_rendu)
                if limite and premier:
                    avec_echeance += 1
                    a_temps += 1 if premier <= limite else 0
        total_attrib = perf.missions_terminees + perf.missions_retirees
        if delais:
            perf.delai_moyen_jours = statistics.mean(delais)
            if len(delais) >= 2 and perf.delai_moyen_jours > 0:
                cv = statistics.pstdev(delais) / perf.delai_moyen_jours
                perf.regularite = max(0.0, 1 - min(cv, 1.0))
        if vitesses:
            perf.rapidite_min_par_jour = statistics.mean(vitesses)
        if avec_echeance:
            perf.respect_delais = a_temps / avec_echeance
        if nb_livraisons:
            perf.qualite = max(0.0, 1 - nb_corrections / nb_livraisons)
            perf.conformite_docx = nb_conformes / nb_livraisons
        if total_attrib:
            perf.fiabilite = perf.missions_terminees / total_attrib
        if perf.missions_terminees >= SEUIL_BONNE:
            perf.fiabilite_donnees = "bonne"
        elif perf.missions_terminees >= SEUIL_FIABLE:
            perf.fiabilite_donnees = "limitee"
        result[str(p.id)] = perf
    return result


def suggestions(db: Session, dossier: Dossier) -> List[dict]:
    """Classement explicable des retranscripteurs pour un dossier."""
    perfs = performances(db)
    type_instance = dossier.type_instance.value
    lignes = []
    for perf in perfs.values():
        raisons, alertes = [], []
        historique_utilise = perf.fiabilite_donnees != "insuffisante"
        composantes = []
        if historique_utilise:
            for valeur, poids, libelle in (
                (perf.qualite, 0.30, "qualité"),
                (perf.respect_delais, 0.25, "respect des délais"),
                (perf.fiabilite, 0.15, "fiabilité"),
                (perf.regularite, 0.10, "régularité"),
                (min(perf.rapidite_min_par_jour / 60, 1.0) if perf.rapidite_min_par_jour else None, 0.10, "rapidité"),
                (perf.conformite_docx, 0.10, "conformité des documents"),
            ):
                if valeur is not None:
                    composantes.append((valeur, poids))
                    if valeur >= 0.85:
                        raisons.append(f"Très bon niveau de {libelle}")
                    elif valeur < 0.6:
                        alertes.append(f"{libelle.capitalize()} à surveiller")
        historique = (sum(v * w for v, w in composantes) / sum(w for _, w in composantes)) if composantes else None

        nb_meme_type = perf.missions_par_instance.get(type_instance, 0)
        specialiste = type_instance in perf.specialites_declarees or nb_meme_type >= 2
        if specialiste:
            raisons.append(f"Expérience des instances {type_instance}"
                           + (f" ({nb_meme_type} mission(s))" if nb_meme_type else " (déclarée)"))
        if perf.charge_actuelle == 0:
            raisons.append("Aucune mission en cours")
        else:
            (alertes if perf.charge_actuelle >= 3 else raisons).append(
                f"{perf.charge_actuelle} mission(s) en cours ({perf.minutes_en_cours} min d'audio)")
        if not perf.disponible:
            alertes.insert(0, "Indiqué(e) comme indisponible")
        if not historique_utilise:
            alertes.append(f"Données insuffisantes ({perf.missions_terminees} mission(s) terminée(s))")

        base = historique if historique is not None else 0.5
        score = base + (0.10 if specialiste else 0) - min(perf.charge_actuelle * 0.08, 0.40)
        if not perf.disponible:
            score -= 1.0
        lignes.append({
            "prestataire_id": perf.prestataire_id,
            "nom": perf.nom,
            "score": round(max(min(score, 1.0), 0.0) * 100),
            "disponible": perf.disponible,
            "charge_actuelle": perf.charge_actuelle,
            "fiabilite_donnees": perf.fiabilite_donnees,
            "raisons": raisons,
            "alertes": alertes,
            "indicateurs": perf.dict(),
            "_tri": score,
        })
    lignes.sort(key=lambda l: l["_tri"], reverse=True)
    for rang, l in enumerate(lignes, start=1):
        l.pop("_tri")
        l["rang"] = rang
    return lignes


def charge_reelle(db: Session, prestataire_id) -> int:
    return db.query(Affectation).join(Dossier, Dossier.id == Affectation.dossier_id).filter(
        Affectation.prestataire_id == prestataire_id,
        Affectation.statut.in_(ACTIVES),
        Dossier.statut_production.notin_(["valide", "archive"]),
    ).count()
