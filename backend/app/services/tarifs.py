"""
Tarifs administrables.

Chaque grille est une VERSION ; les versions d'une même grille partagent `famille_id`.
Cycle : brouillon → publiée (dates d'application) → remplacée par une nouvelle version
(la précédente reçoit une date de fin et reste en historique) ou désactivée.

Non-rétroactivité :
- la grille applicable est choisie à la DATE DE RÉFÉRENCE du dossier (réception de l'audio),
  pas à la date du jour : publier un nouveau tarif ne change rien aux dossiers déjà reçus ;
- une grille ayant servi à un calcul n'est plus modifiable : toute modification crée une version ;
- chaque calcul conserve une copie intégrale des grilles et règles appliquées.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.prestataire import Prestataire
from app.models.pricing.calcul import CalculTarifaire
from app.models.pricing.grille import GrilleTarifaire, TypeGrilleEnum, CibleGrilleEnum
from app.models.pricing.regle import RegleTarifaire, TypeRegleEnum, ConditionTypeEnum, ModeCalculEnum
from app.services.pricing.engine import CriteresDossier, PricingEngine

MAJORATIONS = (TypeGrilleEnum.URGENCE, TypeGrilleEnum.SNP, TypeGrilleEnum.SPECIAL)
CONDITIONS_URGENCE_DEFAUT = {"case_cochee": True, "dossier_signale_urgent": True, "delai_max_jours": None}


# ── États d'une version ──────────────────────────────────────────────────────
def statut_version(g: GrilleTarifaire, today: Optional[date] = None) -> str:
    today = today or date.today()
    if g.brouillon:
        return "brouillon"
    if not g.active:
        return "desactivee"
    if g.date_debut > today:
        return "programmee"
    if g.date_fin and g.date_fin < today:
        return "archivee"
    return "en_vigueur"


def famille(g: GrilleTarifaire) -> uuid.UUID:
    return g.famille_id or g.id


def grille_utilisee(db: Session, grille_id) -> bool:
    """Vrai si la version a servi à au moins un calcul (quel que soit son statut)."""
    gid = str(grille_id)
    return any(snap and gid in snap for (snap,) in db.query(CalculTarifaire.grilles_version_snap).all())


# ── Sélection de la grille applicable ────────────────────────────────────────
def _famille_attribuee(db: Session, grille_id) -> Optional[uuid.UUID]:
    if not grille_id:
        return None
    g = db.query(GrilleTarifaire).filter(GrilleTarifaire.id == grille_id).first()
    return famille(g) if g else None


def grille_applicable(
    db: Session, type_grille: TypeGrilleEnum, date_ref: date, type_instance: Optional[str] = None,
    client_id=None, prestataire_id=None,
) -> Optional[GrilleTarifaire]:
    """Choisit la version publiée en vigueur à `date_ref`, de la plus spécifique à la plus générale :
    cible explicite (4) > grille attribuée sur la fiche (3) > type d'instance (2) > grille par défaut (1)."""
    candidates = db.query(GrilleTarifaire).filter(
        GrilleTarifaire.type == type_grille,
        GrilleTarifaire.active == True,  # noqa: E712
        GrilleTarifaire.brouillon == False,  # noqa: E712
        GrilleTarifaire.date_debut <= date_ref,
    ).filter((GrilleTarifaire.date_fin == None) | (GrilleTarifaire.date_fin >= date_ref)).all()  # noqa: E711

    entite_id, fam_attr = None, None
    if type_grille == TypeGrilleEnum.RETRANSCRIPTEUR or type_grille == TypeGrilleEnum.CORRECTEUR:
        entite_id = prestataire_id
        p = db.query(Prestataire).filter(Prestataire.id == prestataire_id).first() if prestataire_id else None
        fam_attr = _famille_attribuee(db, p.grille_tarifaire_id) if p else None
    else:
        entite_id = client_id
        c = db.query(Client).filter(Client.id == client_id).first() if client_id else None
        fam_attr = _famille_attribuee(db, c.grille_tarifaire_id) if c else None

    def score(g: GrilleTarifaire) -> int:
        if g.type_instance and g.type_instance != type_instance:
            return 0
        if g.cible != CibleGrilleEnum.GLOBAL:
            if entite_id and g.cible_id == entite_id:
                return 4
            if fam_attr and famille(g) == fam_attr:
                return 3
            return 0  # grille « sur attribution » non attribuée à cette fiche
        if fam_attr and famille(g) == fam_attr:
            return 3
        return 2 if g.type_instance else 1

    scored = [(score(g), g) for g in candidates]
    scored = [(s, g) for s, g in scored if s > 0]
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], x[1].date_debut, x[1].date_creation or datetime.min.replace(tzinfo=timezone.utc)),
                reverse=True)
    return scored[0][1]


# ── Majorations ──────────────────────────────────────────────────────────────
def majoration_declenchee(g: GrilleTarifaire, criteres: dict, est_urgent: bool,
                          date_reception: Optional[date], date_limite: Optional[date]) -> bool:
    if g.type == TypeGrilleEnum.SNP:
        return bool(criteres.get("sans_prise_de_note"))
    if g.type == TypeGrilleEnum.SPECIAL:
        return bool(criteres.get("prestation_speciale"))
    c = {**CONDITIONS_URGENCE_DEFAUT, **(g.conditions or {})}
    if c.get("case_cochee") and criteres.get("urgence"):
        return True
    if c.get("dossier_signale_urgent") and est_urgent:
        return True
    delai = c.get("delai_max_jours")
    if delai is not None and date_reception and date_limite:
        return (date_limite - date_reception).days <= int(delai)
    return False


# ── Calcul (persisté ou simulé) ──────────────────────────────────────────────
@dataclass
class Contexte:
    type_instance: str
    nombre_pages: Decimal
    date_reference: date
    client_id: Optional[uuid.UUID] = None
    retranscripteur_id: Optional[uuid.UUID] = None
    correcteur_id: Optional[uuid.UUID] = None
    criteres: dict = field(default_factory=dict)
    est_urgent: bool = False
    date_limite: Optional[date] = None


@dataclass
class Resultat:
    montant_client: Decimal
    montant_retranscripteur: Decimal
    montant_correcteur: Decimal
    lignes: list
    grilles: List[GrilleTarifaire]
    majorations: List[str]
    grille_client: Optional[GrilleTarifaire]
    grille_retranscripteur: Optional[GrilleTarifaire]


def calculer(db: Session, ctx: Contexte) -> Resultat:
    engine = PricingEngine(db)
    crit = ctx.criteres or {}
    grille_client = grille_applicable(db, TypeGrilleEnum.CLIENT, ctx.date_reference, ctx.type_instance,
                                      client_id=ctx.client_id)
    if not grille_client:
        raise HTTPException(status_code=400, detail="Aucune grille tarifaire client en vigueur à la date du dossier : "
                                                    "calcul impossible")
    # Sans retranscripteur désigné : grille par défaut (comportement historique du calcul)
    grille_retrans = grille_applicable(db, TypeGrilleEnum.RETRANSCRIPTEUR, ctx.date_reference, ctx.type_instance,
                                       prestataire_id=ctx.retranscripteur_id)

    cote_client, cote_retrans, majorations = [grille_client], [g for g in [grille_retrans] if g], []
    urgence_effective = False
    for t in MAJORATIONS:
        g = grille_applicable(db, t, ctx.date_reference, ctx.type_instance, client_id=ctx.client_id)
        if not g or not majoration_declenchee(g, crit, ctx.est_urgent, ctx.date_reference, ctx.date_limite):
            continue
        majorations.append(g.nom)
        if t == TypeGrilleEnum.URGENCE:
            urgence_effective = True
        if g.applique_client:
            cote_client.append(g)
        if g.applique_retranscripteur and cote_retrans:
            cote_retrans.append(g)

    criteres = CriteresDossier(
        type_instance=ctx.type_instance, urgence=urgence_effective,
        sans_prise_de_note=bool(crit.get("sans_prise_de_note")),
        prestation_speciale=bool(crit.get("prestation_speciale")),
        type_prestation_speciale=crit.get("type_prestation_speciale"),
        nombre_pages=ctx.nombre_pages, client_id=ctx.client_id,
        retranscripteur_id=ctx.retranscripteur_id, correcteur_id=ctx.correcteur_id,
    )
    montant_client, lignes_client = engine._calcul_cote(cote_client, criteres, "CLIENT")
    montant_retrans, lignes_retrans = (engine._calcul_cote(cote_retrans, criteres, "RETRANSCRIPTEUR")
                                       if cote_retrans else (Decimal("0.00"), []))
    montant_correct, lignes_correct, cote_correct = Decimal("0.00"), [], []
    if ctx.correcteur_id:  # pas de correcteur externe aujourd'hui : aucun montant sans affectation
        gc = grille_applicable(db, TypeGrilleEnum.CORRECTEUR, ctx.date_reference, ctx.type_instance,
                               prestataire_id=ctx.correcteur_id)
        if gc:
            cote_correct = [gc]
            montant_correct, lignes_correct = engine._calcul_cote(cote_correct, criteres, "CORRECTEUR")
    grilles = list({g.id: g for g in cote_client + cote_retrans + cote_correct}.values())
    return Resultat(montant_client, montant_retrans, montant_correct, lignes_client + lignes_retrans + lignes_correct,
                    grilles, majorations, grille_client, grille_retrans)


# ── Copie intégrale des paramètres appliqués ─────────────────────────────────
def _val(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    return getattr(v, "value", v)


def snapshot(db: Session, g: GrilleTarifaire) -> dict:
    regles = db.query(RegleTarifaire).filter(RegleTarifaire.grille_id == g.id, RegleTarifaire.actif == True) \
        .order_by(RegleTarifaire.priorite).all()  # noqa: E712
    return {
        "nom": g.nom, "version": g.version, "type": g.type.value, "cible": g.cible.value,
        "cible_id": _val(g.cible_id), "famille_id": _val(famille(g)), "type_instance": g.type_instance,
        "date_debut": _val(g.date_debut), "date_fin": _val(g.date_fin),
        "applique_client": g.applique_client, "applique_retranscripteur": g.applique_retranscripteur,
        "conditions": g.conditions,
        "regles": [{k: _val(getattr(r, k)) for k in ("libelle", "type_regle", "condition_type", "condition_valeur",
                                                     "mode_calcul", "valeur", "unite", "priorite", "plafond_montant")}
                   for r in regles],
    }


# ── Représentations simplifiées (interface) ──────────────────────────────────
def tranches(db: Session, g: GrilleTarifaire) -> Optional[List[dict]]:
    """Grille exprimée en tranches de pages, ou None si elle contient des règles avancées."""
    regles = db.query(RegleTarifaire).filter(RegleTarifaire.grille_id == g.id, RegleTarifaire.actif == True).all()  # noqa: E712
    out = []
    for r in regles:
        if r.type_regle != TypeRegleEnum.BASE or r.mode_calcul not in (ModeCalculEnum.FORFAIT_FIXE, ModeCalculEnum.PAR_PAGE):
            return None
        if r.condition_type == ConditionTypeEnum.TOUJOURS:
            mini = Decimal("0")
        elif r.condition_type == ConditionTypeEnum.SI_VOLUME:
            mini = Decimal(str((r.condition_valeur or {}).get("pages_min", 0)))
        else:
            return None
        out.append({"pages_min": mini, "mode": "forfait" if r.mode_calcul == ModeCalculEnum.FORFAIT_FIXE else "par_page",
                    "montant": r.valeur})
    return sorted(out, key=lambda t: t["pages_min"]) if out else None


def majoration(db: Session, g: GrilleTarifaire) -> Optional[dict]:
    regles = db.query(RegleTarifaire).filter(RegleTarifaire.grille_id == g.id, RegleTarifaire.actif == True).all()  # noqa: E712
    if len(regles) != 1 or regles[0].type_regle != TypeRegleEnum.MAJORATION or regles[0].mode_calcul not in (
            ModeCalculEnum.POURCENTAGE_BASE, ModeCalculEnum.FORFAIT_FIXE):
        return None
    r = regles[0]
    return {"mode": "pourcentage" if r.mode_calcul == ModeCalculEnum.POURCENTAGE_BASE else "montant", "valeur": r.valeur}


def ecrire_tranches(db: Session, g: GrilleTarifaire, items: List[dict], prefixe: str) -> None:
    db.query(RegleTarifaire).filter(RegleTarifaire.grille_id == g.id).delete()
    ordre = sorted(items, key=lambda t: Decimal(str(t["pages_min"])), reverse=True)
    for i, t in enumerate(ordre):
        mini = Decimal(str(t["pages_min"]))
        par_page = t["mode"] == "par_page"
        libelle = (f"{prefixe} {'plus de ' + str(int(mini)) if mini != mini.to_integral_value() else 'dès ' + str(int(mini))} pages"
                   if mini > 1 else f"{prefixe} première tranche")
        db.add(RegleTarifaire(
            grille_id=g.id, libelle=f"{libelle} → {t['montant']} {'€/page' if par_page else '€'}",
            type_regle=TypeRegleEnum.BASE,
            condition_type=ConditionTypeEnum.TOUJOURS if mini <= 1 else ConditionTypeEnum.SI_VOLUME,
            condition_valeur=None if mini <= 1 else {"pages_min": str(mini)},
            mode_calcul=ModeCalculEnum.PAR_PAGE if par_page else ModeCalculEnum.FORFAIT_FIXE,
            valeur=Decimal(str(t["montant"])), unite="€/page" if par_page else "€",
            priorite=1000 if mini <= 1 else 10 * (i + 1), cumulable=True, actif=True,
        ))


def ecrire_majoration(db: Session, g: GrilleTarifaire, mode: str, valeur: Decimal) -> None:
    db.query(RegleTarifaire).filter(RegleTarifaire.grille_id == g.id).delete()
    pct = mode == "pourcentage"
    db.add(RegleTarifaire(
        grille_id=g.id, libelle=f"{g.nom} : +{valeur}{' %' if pct else ' €'}", type_regle=TypeRegleEnum.MAJORATION,
        condition_type=ConditionTypeEnum.TOUJOURS, mode_calcul=ModeCalculEnum.POURCENTAGE_BASE if pct else ModeCalculEnum.FORFAIT_FIXE,
        valeur=Decimal(str(valeur)), unite="%" if pct else "€", priorite=50, cumulable=True, actif=True,
    ))


# ── Versions ────────────────────────────────────────────────────────────────
def prochaine_version(db: Session, g: GrilleTarifaire) -> str:
    fam = famille(g)
    versions = [v for (v,) in db.query(GrilleTarifaire.version).filter(
        (GrilleTarifaire.famille_id == fam) | (GrilleTarifaire.id == fam)).all()]
    majeurs = []
    for v in versions:
        try:
            majeurs.append(int(str(v).split(".")[0]))
        except ValueError:
            pass
    return f"{max(majeurs, default=0) + 1}.0"


def nouvelle_version(db: Session, source: GrilleTarifaire, user_id) -> GrilleTarifaire:
    """Copie la version en brouillon (mêmes règles) ; l'originale reste intacte pour l'historique."""
    copie = GrilleTarifaire(
        nom=source.nom, type=source.type, cible=source.cible, cible_id=source.cible_id,
        version=prochaine_version(db, source), date_debut=date.today(), date_fin=None, active=False, brouillon=True,
        description=source.description, creee_par_id=user_id, famille_id=famille(source),
        type_instance=source.type_instance, applique_client=source.applique_client,
        applique_retranscripteur=source.applique_retranscripteur, conditions=source.conditions,
    )
    db.add(copie)
    db.flush()
    for r in db.query(RegleTarifaire).filter(RegleTarifaire.grille_id == source.id, RegleTarifaire.actif == True).all():  # noqa: E712
        db.add(RegleTarifaire(
            grille_id=copie.id, libelle=r.libelle, type_regle=r.type_regle, condition_type=r.condition_type,
            condition_valeur=r.condition_valeur, mode_calcul=r.mode_calcul, valeur=r.valeur, unite=r.unite,
            priorite=r.priorite, cumulable=r.cumulable, plafond_montant=r.plafond_montant, actif=True,
        ))
    db.flush()
    return copie


def publier(db: Session, g: GrilleTarifaire, date_debut: date) -> List[GrilleTarifaire]:
    """Publie un brouillon à partir de `date_debut` (jamais dans le passé) ; clôt la version précédente.
    Retourne les versions clôturées."""
    if not g.brouillon:
        raise HTTPException(status_code=409, detail="Seul un brouillon peut être publié")
    if date_debut < date.today():
        raise HTTPException(status_code=400, detail="La date d'application ne peut pas être dans le passé "
                                                    "(aucune modification rétroactive)")
    if not db.query(RegleTarifaire).filter(RegleTarifaire.grille_id == g.id, RegleTarifaire.actif == True).count():  # noqa: E712
        raise HTTPException(status_code=400, detail="La grille ne contient aucune règle")
    fam = famille(g)
    autres = db.query(GrilleTarifaire).filter(
        GrilleTarifaire.id != g.id, GrilleTarifaire.brouillon == False, GrilleTarifaire.active == True,  # noqa: E712
        (GrilleTarifaire.famille_id == fam) | (GrilleTarifaire.id == fam),
    ).all()
    if any(o.date_debut >= date_debut for o in autres):
        raise HTTPException(status_code=409, detail="Une version de cette grille est déjà programmée à cette date "
                                                    "ou après : désactivez-la d'abord")
    closes = []
    for o in autres:
        if o.date_fin is None or o.date_fin >= date_debut:
            o.date_fin = date_debut - timedelta(days=1)
            closes.append(o)
    g.brouillon = False
    g.active = True
    g.date_debut = date_debut
    g.date_fin = None
    return closes
