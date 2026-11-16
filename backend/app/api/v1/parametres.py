"""
Délais de réalisation et paramètres métier — administrables par la cliente.

Une modification des règles recalcule les échéances encore prévisionnelles (dossiers non attribués,
échéance calculée) et ne touche jamais une échéance figée à l'attribution ou saisie à la main.
Chaque recalcul est tracé dans l'historique du dossier.
"""
import uuid
from datetime import date, datetime, timezone
from typing import Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.core.deps import DbDep, require_permission
from app.models.dossier import TypeInstanceEnum
from app.models.journal import TypeActionEnum
from app.models.refonte import Parametre, RegleDelai
from app.models.user import User
from app.services import delais
from app.services.journal import log_action

router = APIRouter(prefix="/parametres")

LIRE = require_permission("tarifs.gerer", "dossiers.gerer")
ECRIRE = require_permission("tarifs.gerer")
INSTANCES = {t.value for t in TypeInstanceEnum}


class RegleIn(BaseModel):
    libelle: str = Field(min_length=2, max_length=200)
    actif: bool = True
    priorite: int = Field(default=100, ge=0, le=10000)
    type_instance: Optional[str] = None
    duree_min_minutes: Optional[int] = Field(default=None, ge=0, le=6000)
    duree_max_minutes: Optional[int] = Field(default=None, ge=1, le=6000)
    urgence: Optional[bool] = None
    prestation: Optional[Literal["snp", "special"]] = None
    delai_jours: int = Field(ge=0, le=365)
    type_jours: Literal["calendaires", "ouvres"] = "calendaires"
    description: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _ok(self):
        if self.type_instance and self.type_instance not in INSTANCES:
            raise ValueError("Type d'instance inconnu")
        if self.duree_min_minutes is not None and self.duree_max_minutes is not None \
                and self.duree_max_minutes <= self.duree_min_minutes:
            raise ValueError("La durée maximale doit être supérieure à la durée minimale")
        return self


class Generaux(BaseModel):
    valeurs: Dict[str, Optional[int]]

    @model_validator(mode="after")
    def _ok(self):
        for k, v in self.valeurs.items():
            if k not in delais.PARAMETRES:
                raise ValueError(f"Paramètre inconnu : {k}")
            if v is not None and not 0 <= v <= 1000:
                raise ValueError(f"Valeur hors limites pour {k}")
        return self


class Simulation(BaseModel):
    date_reception: date
    type_instance: str = "CE"
    duree_minutes: Optional[int] = Field(default=None, ge=0, le=6000)
    urgence: bool = False
    sans_prise_de_note: bool = False
    prestation_speciale: bool = False


def regle_out(r: RegleDelai) -> dict:
    return {k: getattr(r, k) for k in ("libelle", "actif", "priorite", "type_instance", "duree_min_minutes",
                                       "duree_max_minutes", "urgence", "prestation", "delai_jours", "type_jours",
                                       "description", "modifie_le")} | {"id": str(r.id)}


def _regle(db, regle_id: uuid.UUID) -> RegleDelai:
    r = db.query(RegleDelai).filter(RegleDelai.id == regle_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Règle introuvable")
    return r


def _log(db, user, action: str, detail: dict):
    log_action(db, TypeActionEnum.CONFIG_GRILLE, utilisateur_id=user.id, detail={"action": action, **detail})


@router.get("/delais")
def lire(db: DbDep, _u: User = Depends(LIRE)):
    return {
        "regles": [regle_out(r) for r in db.query(RegleDelai).order_by(RegleDelai.priorite, RegleDelai.libelle).all()],
        "generaux": [{"cle": k, "libelle": lib, "valeur": delais.parametre(db, k)} for k, lib in delais.PARAMETRES.items()],
    }


@router.post("/delais/regles", status_code=201)
def creer(payload: RegleIn, db: DbDep, user: User = Depends(ECRIRE)):
    r = RegleDelai(**payload.model_dump(), modifie_par_id=user.id)
    db.add(r)
    db.flush()
    _log(db, user, "creation_regle_delai", {"regle": regle_out(r) | {"modifie_le": None}})
    n = delais.recalculer_non_attribues(db, user.id)
    db.commit()
    return regle_out(r) | {"echeances_recalculees": n}


@router.put("/delais/regles/{regle_id}")
def modifier(regle_id: uuid.UUID, payload: RegleIn, db: DbDep, user: User = Depends(ECRIRE)):
    r = _regle(db, regle_id)
    avant = regle_out(r) | {"modifie_le": None}
    for k, v in payload.model_dump().items():
        setattr(r, k, v)
    r.modifie_par_id, r.modifie_le = user.id, datetime.now(timezone.utc)
    _log(db, user, "modification_regle_delai", {"avant": avant, "apres": regle_out(r) | {"modifie_le": None}})
    db.flush()
    n = delais.recalculer_non_attribues(db, user.id)
    db.commit()
    return regle_out(r) | {"echeances_recalculees": n}


@router.delete("/delais/regles/{regle_id}", status_code=204)
def supprimer(regle_id: uuid.UUID, db: DbDep, user: User = Depends(ECRIRE)):
    r = _regle(db, regle_id)
    # Les dossiers conservent leur échéance et une copie de la règle utilisée (echeance_detail)
    _log(db, user, "suppression_regle_delai", {"regle": regle_out(r) | {"modifie_le": None}})
    db.delete(r)
    db.flush()
    delais.recalculer_non_attribues(db, user.id)
    db.commit()


@router.put("/generaux")
def generaux(payload: Generaux, db: DbDep, user: User = Depends(ECRIRE)):
    for cle, val in payload.valeurs.items():
        p = db.query(Parametre).filter(Parametre.cle == cle).first()
        avant = p.valeur.get("valeur") if p and p.valeur else None
        if not p:
            p = Parametre(cle=cle)
            db.add(p)
        p.valeur = {"valeur": val}
        p.modifie_par_id, p.modifie_le = user.id, datetime.now(timezone.utc)
        _log(db, user, "modification_parametre", {"cle": cle, "avant": avant, "apres": val})
    db.commit()
    return lire(db, user)


@router.post("/delais/simuler")
def simuler(payload: Simulation, db: DbDep, _u: User = Depends(LIRE)):
    ech, detail = delais.echeance_prevue(db, payload.date_reception, payload.type_instance, payload.duree_minutes, {
        "urgence": payload.urgence, "sans_prise_de_note": payload.sans_prise_de_note,
        "prestation_speciale": payload.prestation_speciale})
    return {"echeance": ech, "detail": detail,
            "message": None if ech else "Aucune règle de délai ne correspond : l'échéance devra être saisie."}
