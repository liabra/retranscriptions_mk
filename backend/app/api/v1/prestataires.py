import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.core.deps import DbDep, require_permission, require_admin, client_ip
from app.core.permissions import has_permission
from app.core.security import encrypt_iban, decrypt_iban, hash_password, generate_password
from app.models.dossier import TypeInstanceEnum
from app.models.journal import TypeActionEnum
from app.models.prestataire import Prestataire, RolePrestaEnum
from app.models.user import User, RoleEnum
from app.services.attribution import performances, charge_reelle
from app.services.journal import log_action

router = APIRouter()

_TYPES = {t.value for t in TypeInstanceEnum}


class PrestaCreate(BaseModel):
    nom: str = Field(min_length=2, max_length=255)
    email: EmailStr
    telephone: Optional[str] = Field(default=None, max_length=50)
    disponible: bool = True
    iban: Optional[str] = Field(default=None, max_length=50)
    grille_tarifaire_id: Optional[uuid.UUID] = None
    specialites: Optional[List[str]] = None
    notes_internes: Optional[str] = Field(default=None, max_length=5000)


class PrestaUpdate(BaseModel):
    nom: Optional[str] = Field(default=None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    telephone: Optional[str] = Field(default=None, max_length=50)
    disponible: Optional[bool] = None
    iban: Optional[str] = Field(default=None, max_length=50)
    grille_tarifaire_id: Optional[uuid.UUID] = None
    actif: Optional[bool] = None
    specialites: Optional[List[str]] = None
    notes_internes: Optional[str] = Field(default=None, max_length=5000)


def presta_out(db, p: Prestataire) -> dict:
    compte = db.query(User).filter(User.prestataire_id == p.id).first()
    return {
        "id": str(p.id), "nom": p.nom, "email": p.email, "telephone": p.telephone,
        "disponible": p.disponible, "actif": p.actif, "charge_actuelle": charge_reelle(db, p.id),
        "grille_tarifaire_id": str(p.grille_tarifaire_id) if p.grille_tarifaire_id else None,
        "specialites": p.specialites or [], "notes_internes": p.notes_internes,
        "iban_renseigne": bool(p.iban_chiffre),
        "compte": {"id": str(compte.id), "email": compte.email, "actif": compte.actif,
                   "last_login": compte.last_login} if compte else None,
    }


def _specialites(values: Optional[List[str]]) -> Optional[List[str]]:
    if values is None:
        return None
    bad = [v for v in values if v not in _TYPES]
    if bad:
        raise HTTPException(status_code=400, detail=f"Spécialité inconnue : {', '.join(bad)}")
    return sorted(set(values))


@router.get("")
def lister(db: DbDep, _u: User = Depends(require_permission("prestataires.gerer", "attribution.gerer", "finance.voir")),
           actif_only: bool = True):
    q = db.query(Prestataire).filter(Prestataire.role != RolePrestaEnum.CORRECTEUR)
    if actif_only:
        q = q.filter(Prestataire.actif == True)  # noqa: E712
    return [presta_out(db, p) for p in q.order_by(Prestataire.nom).all()]


@router.post("", status_code=201)
def creer(payload: PrestaCreate, db: DbDep, user: User = Depends(require_permission("prestataires.gerer"))):
    if payload.grille_tarifaire_id and not has_permission(user, "tarifs.gerer"):
        raise HTTPException(status_code=403, detail="Attribuer une grille de rémunération requiert le droit de gérer les tarifs")
    data = payload.model_dump(exclude={"iban", "specialites"})
    p = Prestataire(**data, role=RolePrestaEnum.RETRANSCRIPTEUR, specialites=_specialites(payload.specialites))
    if payload.iban:
        p.iban_chiffre = encrypt_iban(payload.iban.replace(" ", "").upper())
    db.add(p)
    db.flush()
    log_action(db, TypeActionEnum.NOTE, utilisateur_id=user.id,
               detail={"action": "creation_prestataire", "prestataire_id": str(p.id)})
    db.commit()
    return presta_out(db, p)


@router.get("/performances")
def indicateurs(db: DbDep, _u: User = Depends(require_permission("prestataires.performance"))):
    return [perf.dict() for perf in performances(db).values()]


@router.get("/{presta_id}")
def lire(presta_id: uuid.UUID, db: DbDep,
         _u: User = Depends(require_permission("prestataires.gerer", "attribution.gerer", "finance.voir"))):
    p = db.query(Prestataire).filter(Prestataire.id == presta_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Retranscripteur introuvable")
    return presta_out(db, p)


@router.patch("/{presta_id}")
def modifier(presta_id: uuid.UUID, payload: PrestaUpdate, db: DbDep,
             user: User = Depends(require_permission("prestataires.gerer"))):
    p = db.query(Prestataire).filter(Prestataire.id == presta_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Retranscripteur introuvable")
    data = payload.model_dump(exclude_unset=True, exclude={"iban"})
    if "grille_tarifaire_id" in data and data["grille_tarifaire_id"] != p.grille_tarifaire_id \
            and not has_permission(user, "tarifs.gerer"):
        raise HTTPException(status_code=403, detail="Attribuer une grille de rémunération requiert le droit de gérer les tarifs")
    if "specialites" in data:
        data["specialites"] = _specialites(data["specialites"])
    if "iban" in payload.model_fields_set:
        if user.role != RoleEnum.ADMINISTRATRICE:
            raise HTTPException(status_code=403, detail="IBAN modifiable uniquement par l'administratrice")
        p.iban_chiffre = encrypt_iban(payload.iban.replace(" ", "").upper()) if payload.iban else None
    for k, v in data.items():
        setattr(p, k, v)
    log_action(db, TypeActionEnum.NOTE, utilisateur_id=user.id,
               detail={"action": "modification_prestataire", "prestataire_id": str(p.id),
                       "champs": sorted(payload.model_fields_set)})  # fix: l'IBAN n'est jamais journalisé
    db.commit()
    return presta_out(db, p)


@router.get("/{presta_id}/iban")
def lire_iban(presta_id: uuid.UUID, request: Request, db: DbDep, admin: User = Depends(require_admin)):
    p = db.query(Prestataire).filter(Prestataire.id == presta_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Retranscripteur introuvable")
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, utilisateur_id=admin.id, ip_source=client_ip(request),
               detail={"action": "consultation_iban", "prestataire_id": str(p.id)})
    db.commit()
    return {"iban": decrypt_iban(p.iban_chiffre) if p.iban_chiffre else None}


@router.post("/{presta_id}/compte", status_code=201)
def creer_compte(presta_id: uuid.UUID, request: Request, db: DbDep, admin: User = Depends(require_admin)):
    """Crée (ou réinitialise) l'accès du retranscripteur. Le mot de passe temporaire n'est affiché qu'une fois."""
    p = db.query(Prestataire).filter(Prestataire.id == presta_id, Prestataire.actif == True).first()  # noqa: E712
    if not p:
        raise HTTPException(status_code=404, detail="Retranscripteur introuvable ou inactif")
    temp = generate_password()
    compte = db.query(User).filter(User.prestataire_id == p.id).first()
    if compte:
        compte.hashed_password = hash_password(temp)
        compte.must_change_password = True
        compte.actif = True
        compte.token_version = (compte.token_version or 0) + 1
        action = "reinitialisation_compte_prestataire"
    else:
        email = p.email.strip().lower()
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=409, detail="Un compte utilise déjà cet email")
        compte = User(email=email, nom=p.nom, hashed_password=hash_password(temp), role=RoleEnum.RETRANSCRIPTEUR,
                      prestataire_id=p.id, must_change_password=True)
        db.add(compte)
        action = "creation_compte_prestataire"
    db.flush()
    log_action(db, TypeActionEnum.AUTH, utilisateur_id=admin.id, ip_source=client_ip(request),
               detail={"action": action, "prestataire_id": str(p.id), "compte": str(compte.id)})
    db.commit()
    return {"email": compte.email, "mot_de_passe_temporaire": temp}
