"""
Tarifs et paramètres commerciaux — administrables par la cliente, sans intervention technique.

Règles :
- une version publiée n'est jamais modifiée sur place : « Modifier » crée une nouvelle version (brouillon) ;
- une publication s'applique à partir d'une date qui ne peut pas être passée ;
- les dossiers déjà calculés, validés ou facturés ne sont jamais recalculés automatiquement ;
- chaque action est journalisée.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from app.core.deps import DbDep, require_permission
from app.models.client import Client
from app.models.dossier import TypeInstanceEnum
from app.models.journal import TypeActionEnum
from app.models.prestataire import Prestataire
from app.models.pricing.grille import GrilleTarifaire, TypeGrilleEnum, CibleGrilleEnum
from app.models.pricing.regle import RegleTarifaire
from app.models.user import User
from app.services import tarifs
from app.services.journal import log_action

router = APIRouter(prefix="/tarifs")

LIRE = require_permission("tarifs.gerer", "finance.voir")
ECRIRE = require_permission("tarifs.gerer")

USAGES = {
    "client": [TypeGrilleEnum.CLIENT],
    "retranscripteur": [TypeGrilleEnum.RETRANSCRIPTEUR],
    "majorations": list(tarifs.MAJORATIONS),
}
TYPES_MAJ = {"urgence": TypeGrilleEnum.URGENCE, "snp": TypeGrilleEnum.SNP, "special": TypeGrilleEnum.SPECIAL}
INSTANCES = {t.value for t in TypeInstanceEnum}


# ── Schémas ─────────────────────────────────────────────────────────────────
class Tranche(BaseModel):
    pages_min: Decimal = Field(ge=0, le=10000)
    mode: Literal["forfait", "par_page"]
    montant: Decimal = Field(gt=0, le=100000)


class Conditions(BaseModel):
    case_cochee: bool = True
    dossier_signale_urgent: bool = True
    delai_max_jours: Optional[int] = Field(default=None, ge=0, le=90)


def _verifier_tranches(t: Optional[List[Tranche]]):
    if t is None:
        return
    if not 1 <= len(t) <= 40:
        raise ValueError("Entre 1 et 40 tranches")
    seuils = [x.pages_min for x in t]
    if len(set(seuils)) != len(seuils):
        raise ValueError("Deux tranches commencent au même nombre de pages")
    if min(seuils) > 1:
        raise ValueError("La première tranche doit commencer à la page 1")


class GrilleIn(BaseModel):
    nom: str = Field(min_length=2, max_length=200)
    usage: Literal["client", "retranscripteur"]
    application: Literal["defaut", "instance", "attribuee"] = "defaut"
    type_instance: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    tranches: List[Tranche]

    @model_validator(mode="after")
    def _ok(self):
        _verifier_tranches(self.tranches)
        if self.application == "instance" and self.type_instance not in INSTANCES:
            raise ValueError("Type d'instance requis")
        return self


class MajorationIn(BaseModel):
    type: Literal["urgence", "snp", "special"]
    nom: str = Field(min_length=2, max_length=200)
    mode: Literal["pourcentage", "montant"]
    valeur: Decimal = Field(gt=0, le=100000)
    applique_client: bool = True
    applique_retranscripteur: bool = False
    conditions: Optional[Conditions] = None
    description: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _ok(self):
        if not (self.applique_client or self.applique_retranscripteur):
            raise ValueError("La majoration doit s'appliquer au client, au retranscripteur, ou aux deux")
        if self.mode == "pourcentage" and self.valeur > 300:
            raise ValueError("Pourcentage trop élevé (300 % maximum)")
        return self


class Modification(BaseModel):
    """Champs modifiables d'un brouillon (grille ou majoration)."""
    nom: Optional[str] = Field(default=None, min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    application: Optional[Literal["defaut", "instance", "attribuee"]] = None
    type_instance: Optional[str] = None
    tranches: Optional[List[Tranche]] = None
    mode: Optional[Literal["pourcentage", "montant"]] = None
    valeur: Optional[Decimal] = Field(default=None, gt=0, le=100000)
    applique_client: Optional[bool] = None
    applique_retranscripteur: Optional[bool] = None
    conditions: Optional[Conditions] = None

    @model_validator(mode="after")
    def _ok(self):
        _verifier_tranches(self.tranches)
        return self


class Publication(BaseModel):
    date_debut: date


class Revision(Modification):
    publier_le: Optional[date] = None  # renseigné : la nouvelle version est publiée immédiatement


class Simulation(BaseModel):
    nombre_pages: Decimal = Field(gt=0, le=5000)
    type_instance: str = "CE"
    client_id: Optional[uuid.UUID] = None
    prestataire_id: Optional[uuid.UUID] = None
    date_reference: Optional[date] = None
    urgence: bool = False
    sans_prise_de_note: bool = False
    prestation_speciale: bool = False
    date_limite: Optional[date] = None


# ── Sérialisation ───────────────────────────────────────────────────────────
def _application(g: GrilleTarifaire) -> str:
    if g.cible != CibleGrilleEnum.GLOBAL:
        return "attribuee"
    return "instance" if g.type_instance else "defaut"


def _usage(t: TypeGrilleEnum) -> str:
    return "client" if t == TypeGrilleEnum.CLIENT else "retranscripteur" if t == TypeGrilleEnum.RETRANSCRIPTEUR \
        else "majorations" if t in tarifs.MAJORATIONS else "autre"


def version_out(db, g: GrilleTarifaire) -> dict:
    regles = db.query(RegleTarifaire).filter(RegleTarifaire.grille_id == g.id, RegleTarifaire.actif == True) \
        .order_by(RegleTarifaire.priorite).all()  # noqa: E712
    maj = tarifs.majoration(db, g) if g.type in tarifs.MAJORATIONS else None
    tr = tarifs.tranches(db, g) if g.type not in tarifs.MAJORATIONS else None
    return {
        "id": str(g.id), "famille_id": str(tarifs.famille(g)), "nom": g.nom, "type": g.type.value,
        "usage": _usage(g.type), "version": g.version, "statut": tarifs.statut_version(g),
        "date_debut": g.date_debut, "date_fin": g.date_fin, "active": g.active, "brouillon": g.brouillon,
        "application": _application(g), "type_instance": g.type_instance, "description": g.description,
        "applique_client": g.applique_client, "applique_retranscripteur": g.applique_retranscripteur,
        "conditions": ({**tarifs.CONDITIONS_URGENCE_DEFAUT, **(g.conditions or {})}
                       if g.type == TypeGrilleEnum.URGENCE else None),
        "tranches": [{"pages_min": t["pages_min"], "mode": t["mode"], "montant": t["montant"]} for t in tr] if tr else None,
        "majoration": maj,
        "avancee": (tr is None and g.type not in tarifs.MAJORATIONS) or (g.type in tarifs.MAJORATIONS and maj is None),
        "regles": [{"libelle": r.libelle, "valeur": r.valeur, "unite": r.unite} for r in regles],
        "utilisee": tarifs.grille_utilisee(db, g.id),
        "creee_par": g.creee_par.nom if g.creee_par else None, "date_creation": g.date_creation,
    }


def _attributions(db, fam: uuid.UUID) -> List[str]:
    noms = []
    for model in (Client, Prestataire):
        for e in db.query(model).filter(model.grille_tarifaire_id.isnot(None), model.actif == True).all():  # noqa: E712
            g = db.query(GrilleTarifaire).filter(GrilleTarifaire.id == e.grille_tarifaire_id).first()
            if g and tarifs.famille(g) == fam:
                noms.append(e.nom)
    return noms


def _get(db, grille_id: uuid.UUID) -> GrilleTarifaire:
    g = db.query(GrilleTarifaire).filter(GrilleTarifaire.id == grille_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grille introuvable")
    return g


def _log(db, user, action: str, g: GrilleTarifaire, extra: Optional[dict] = None):
    log_action(db, TypeActionEnum.CONFIG_GRILLE, utilisateur_id=user.id, detail={
        "action": action, "grille_id": str(g.id), "famille_id": str(tarifs.famille(g)),
        "nom": g.nom, "version": g.version, **(extra or {}),
    })


# ── Lecture ─────────────────────────────────────────────────────────────────
@router.get("/catalogue")
def catalogue(db: DbDep, _u: User = Depends(LIRE),
              usage: str = Query(default="client", pattern="^(client|retranscripteur|majorations)$")):
    grilles = db.query(GrilleTarifaire).filter(GrilleTarifaire.type.in_(USAGES[usage])).all()
    familles = {}
    for g in grilles:
        familles.setdefault(tarifs.famille(g), []).append(g)
    out = []
    for fam, versions in familles.items():
        versions.sort(key=lambda v: (v.date_debut, v.date_creation), reverse=True)
        vs = [version_out(db, v) for v in versions]
        courante = next((v for v in vs if v["statut"] == "en_vigueur"), None) \
            or next((v for v in vs if v["statut"] == "programmee"), None)
        out.append({
            "famille_id": str(fam), "nom": (courante or vs[0])["nom"], "type": vs[0]["type"],
            "courante": courante, "brouillon": next((v for v in vs if v["brouillon"]), None),
            "programmee": next((v for v in vs if v["statut"] == "programmee"), None),
            "versions": vs, "attribuee_a": _attributions(db, fam),
        })
    ordre = {"en_vigueur": 0, "programmee": 1}
    out.sort(key=lambda f: (ordre.get(f["courante"]["statut"], 2) if f["courante"] else 3, f["type"], f["nom"]))
    return out


@router.get("/grilles/{grille_id}")
def lire(grille_id: uuid.UUID, db: DbDep, _u: User = Depends(LIRE)):
    return version_out(db, _get(db, grille_id))


# ── Création / modification de brouillons ───────────────────────────────────
def _appliquer(db, g: GrilleTarifaire, m: Modification) -> None:
    data = m.model_dump(exclude_unset=True)
    if "nom" in data:
        g.nom = m.nom
    if "description" in data:
        g.description = m.description
    if m.application:
        if m.application == "instance" and (m.type_instance or g.type_instance) not in INSTANCES:
            raise HTTPException(status_code=400, detail="Type d'instance requis")
        _set_application(g, m.application, m.type_instance or g.type_instance)
    if g.type in tarifs.MAJORATIONS:
        if m.tranches is not None:
            raise HTTPException(status_code=400, detail="Une majoration n'a pas de tranches")
        if "applique_client" in data:
            g.applique_client = bool(m.applique_client)
        if "applique_retranscripteur" in data:
            g.applique_retranscripteur = bool(m.applique_retranscripteur)
        if not (g.applique_client or g.applique_retranscripteur):
            raise HTTPException(status_code=400, detail="La majoration doit s'appliquer au client et/ou au retranscripteur")
        if m.conditions is not None and g.type == TypeGrilleEnum.URGENCE:
            g.conditions = m.conditions.model_dump()
        if m.mode or m.valeur:
            actuelle = tarifs.majoration(db, g) or {}
            mode, valeur = m.mode or actuelle.get("mode"), m.valeur or actuelle.get("valeur")
            if not mode or not valeur:
                raise HTTPException(status_code=400, detail="Indiquez le type et la valeur de la majoration")
            if mode == "pourcentage" and Decimal(str(valeur)) > 300:
                raise HTTPException(status_code=400, detail="Pourcentage trop élevé (300 % maximum)")
            tarifs.ecrire_majoration(db, g, mode, Decimal(str(valeur)))
    elif m.tranches is not None:
        tarifs.ecrire_tranches(db, g, [t.model_dump() for t in m.tranches], g.nom)


def _set_application(g: GrilleTarifaire, application: str, type_instance: Optional[str]) -> None:
    if application == "attribuee":
        g.cible = CibleGrilleEnum.CLIENT_SPECIFIQUE if g.type == TypeGrilleEnum.CLIENT \
            else CibleGrilleEnum.PRESTATAIRE_SPECIFIQUE
        g.type_instance = None
    else:
        g.cible = CibleGrilleEnum.GLOBAL
        g.type_instance = type_instance if application == "instance" else None
    g.cible_id = None


@router.post("/grilles", status_code=201)
def creer_grille(payload: GrilleIn, db: DbDep, user: User = Depends(ECRIRE)):
    g = GrilleTarifaire(
        nom=payload.nom, type=TypeGrilleEnum.CLIENT if payload.usage == "client" else TypeGrilleEnum.RETRANSCRIPTEUR,
        cible=CibleGrilleEnum.GLOBAL, version="1.0", date_debut=date.today(), active=False, brouillon=True,
        description=payload.description, creee_par_id=user.id,
    )
    _set_application(g, payload.application, payload.type_instance)
    db.add(g)
    db.flush()
    g.famille_id = g.id
    tarifs.ecrire_tranches(db, g, [t.model_dump() for t in payload.tranches], payload.nom)
    _log(db, user, "creation_grille_brouillon", g)
    db.commit()
    return version_out(db, g)


@router.post("/majorations", status_code=201)
def creer_majoration(payload: MajorationIn, db: DbDep, user: User = Depends(ECRIRE)):
    t = TYPES_MAJ[payload.type]
    g = GrilleTarifaire(
        nom=payload.nom, type=t, cible=CibleGrilleEnum.GLOBAL, version="1.0", date_debut=date.today(),
        active=False, brouillon=True, description=payload.description, creee_par_id=user.id,
        applique_client=payload.applique_client, applique_retranscripteur=payload.applique_retranscripteur,
        conditions=(payload.conditions or Conditions()).model_dump() if t == TypeGrilleEnum.URGENCE else None,
    )
    db.add(g)
    db.flush()
    g.famille_id = g.id
    tarifs.ecrire_majoration(db, g, payload.mode, payload.valeur)
    _log(db, user, "creation_majoration_brouillon", g)
    db.commit()
    return version_out(db, g)


@router.put("/grilles/{grille_id}")
def modifier_brouillon(grille_id: uuid.UUID, payload: Modification, db: DbDep, user: User = Depends(ECRIRE)):
    g = _get(db, grille_id)
    if not g.brouillon:
        raise HTTPException(status_code=409, detail="Version publiée : créez une nouvelle version pour la modifier")
    _appliquer(db, g, payload)
    _log(db, user, "modification_brouillon", g, {"champs": sorted(payload.model_fields_set)})
    db.commit()
    return version_out(db, g)


@router.post("/grilles/{grille_id}/reviser", status_code=201)
def reviser(grille_id: uuid.UUID, payload: Revision, db: DbDep, user: User = Depends(ECRIRE)):
    """Crée une nouvelle version à partir d'une version publiée (l'originale reste intacte)."""
    source = _get(db, grille_id)
    if source.brouillon:
        raise HTTPException(status_code=409, detail="Ce brouillon se modifie directement")
    fam = tarifs.famille(source)
    if db.query(GrilleTarifaire).filter(GrilleTarifaire.brouillon == True,  # noqa: E712
                                        (GrilleTarifaire.famille_id == fam) | (GrilleTarifaire.id == fam)).first():
        raise HTTPException(status_code=409, detail="Un brouillon existe déjà pour cette grille : terminez-le ou supprimez-le")
    copie = tarifs.nouvelle_version(db, source, user.id)
    _appliquer(db, copie, payload)
    _log(db, user, "nouvelle_version", copie, {"source": str(source.id)})
    if payload.publier_le:
        db.flush()
        closes = tarifs.publier(db, copie, payload.publier_le)
        _log(db, user, "publication", copie, {"a_partir_du": payload.publier_le.isoformat(),
                                              "versions_cloturees": [str(c.id) for c in closes]})
    db.commit()
    return version_out(db, copie)


@router.post("/grilles/{grille_id}/publier")
def publier(grille_id: uuid.UUID, payload: Publication, db: DbDep, user: User = Depends(ECRIRE)):
    g = _get(db, grille_id)
    closes = tarifs.publier(db, g, payload.date_debut)
    _log(db, user, "publication", g, {"a_partir_du": payload.date_debut.isoformat(),
                                      "versions_cloturees": [str(c.id) for c in closes]})
    db.commit()
    return version_out(db, g)


@router.post("/grilles/{grille_id}/desactiver")
def desactiver(grille_id: uuid.UUID, db: DbDep, user: User = Depends(ECRIRE)):
    g = _get(db, grille_id)
    if g.brouillon:
        raise HTTPException(status_code=409, detail="Un brouillon n'est pas actif")
    g.active = False
    _log(db, user, "desactivation", g)
    db.commit()
    return version_out(db, g)


@router.post("/grilles/{grille_id}/activer")
def activer(grille_id: uuid.UUID, db: DbDep, user: User = Depends(ECRIRE)):
    g = _get(db, grille_id)
    if g.brouillon:
        raise HTTPException(status_code=409, detail="Publiez d'abord ce brouillon")
    fam = tarifs.famille(g)
    chevauche = db.query(GrilleTarifaire).filter(
        GrilleTarifaire.id != g.id, GrilleTarifaire.active == True, GrilleTarifaire.brouillon == False,  # noqa: E712
        (GrilleTarifaire.famille_id == fam) | (GrilleTarifaire.id == fam),
    ).all()
    for o in chevauche:
        if (o.date_fin is None or o.date_fin >= g.date_debut) and (g.date_fin is None or g.date_fin >= o.date_debut):
            raise HTTPException(status_code=409, detail=f"Chevauchement avec la version {o.version} en vigueur sur la même période")
    g.active = True
    _log(db, user, "reactivation", g)
    db.commit()
    return version_out(db, g)


@router.delete("/grilles/{grille_id}", status_code=204)
def supprimer_brouillon(grille_id: uuid.UUID, db: DbDep, user: User = Depends(ECRIRE)):
    g = _get(db, grille_id)
    if not g.brouillon or tarifs.grille_utilisee(db, g.id):
        raise HTTPException(status_code=409, detail="Seul un brouillon jamais utilisé peut être supprimé")
    _log(db, user, "suppression_brouillon", g)
    db.query(RegleTarifaire).filter(RegleTarifaire.grille_id == g.id).delete()
    db.delete(g)
    db.commit()


# ── Simulateur ──────────────────────────────────────────────────────────────
@router.post("/simuler")
def simuler(payload: Simulation, db: DbDep, _u: User = Depends(LIRE)):
    if payload.type_instance not in INSTANCES:
        raise HTTPException(status_code=400, detail="Type d'instance inconnu")
    res = tarifs.calculer(db, tarifs.Contexte(
        type_instance=payload.type_instance, nombre_pages=payload.nombre_pages,
        date_reference=payload.date_reference or date.today(), client_id=payload.client_id,
        retranscripteur_id=payload.prestataire_id, est_urgent=False, date_limite=payload.date_limite,
        criteres={"urgence": payload.urgence, "sans_prise_de_note": payload.sans_prise_de_note,
                  "prestation_speciale": payload.prestation_speciale},
    ))
    return {
        "montant_client": res.montant_client, "montant_retranscripteur": res.montant_retranscripteur,
        "marge": (res.montant_client - res.montant_retranscripteur).quantize(Decimal("0.01")),
        "grille_client": f"{res.grille_client.nom} v{res.grille_client.version}" if res.grille_client else None,
        "grille_retranscripteur": (f"{res.grille_retranscripteur.nom} v{res.grille_retranscripteur.version}"
                                   if res.grille_retranscripteur else None),
        "majorations": res.majorations,
        "lignes": [{"cible": l.cible, "libelle": l.regle_libelle, "montant": l.impact_montant} for l in res.lignes],
        "avertissement": None if payload.prestataire_id else
        "Aucun retranscripteur choisi : rémunération calculée avec la grille par défaut.",
    }
