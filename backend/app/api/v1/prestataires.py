import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator, require_admin
from app.core.security import encrypt_iban, decrypt_iban
from app.models.prestataire import Prestataire
from app.models.user import User
from app.schemas.prestataire import PrestaCreate, PrestaUpdate, PrestaOut

router = APIRouter()


@router.get("/", response_model=List[PrestaOut])
def list_prestataires(
    db: DbDep = Depends(),
    _user: User = Depends(require_admin_or_coordinator),
    actif_only: bool = True,
    disponible_only: bool = False,
):
    q = db.query(Prestataire)
    if actif_only:
        q = q.filter(Prestataire.actif == True)
    if disponible_only:
        q = q.filter(Prestataire.disponible == True)
    return q.order_by(Prestataire.nom).all()


@router.post("/", response_model=PrestaOut, status_code=201)
def create_prestataire(
    payload: PrestaCreate,
    db: DbDep = Depends(),
    _user: User = Depends(require_admin_or_coordinator),
):
    data = payload.model_dump(exclude={"iban"})
    if payload.iban:
        data["iban_chiffre"] = encrypt_iban(payload.iban)

    presta = Prestataire(**data)
    db.add(presta)
    db.commit()
    db.refresh(presta)
    return PrestaOut.model_validate(presta)


@router.get("/{presta_id}", response_model=PrestaOut)
def get_prestataire(
    presta_id: uuid.UUID,
    db: DbDep = Depends(),
    _user: User = Depends(require_admin_or_coordinator),
):
    presta = db.query(Prestataire).filter(Prestataire.id == presta_id).first()
    if not presta:
        raise HTTPException(status_code=404, detail="Prestataire introuvable")
    return PrestaOut.model_validate(presta)


@router.patch("/{presta_id}", response_model=PrestaOut)
def update_prestataire(
    presta_id: uuid.UUID,
    payload: PrestaUpdate,
    db: DbDep = Depends(),
    _user: User = Depends(require_admin_or_coordinator),
):
    presta = db.query(Prestataire).filter(Prestataire.id == presta_id).first()
    if not presta:
        raise HTTPException(status_code=404, detail="Prestataire introuvable")

    data = payload.model_dump(exclude_unset=True, exclude={"iban"})
    if payload.iban is not None:
        data["iban_chiffre"] = encrypt_iban(payload.iban) if payload.iban else None

    for field, value in data.items():
        setattr(presta, field, value)

    db.commit()
    db.refresh(presta)
    return PrestaOut.model_validate(presta)


@router.get("/{presta_id}/iban")
def get_iban(
    presta_id: uuid.UUID,
    db: DbDep = Depends(),
    _admin: User = Depends(require_admin),
):
    """IBAN déchiffré — réservé administratrice uniquement."""
    presta = db.query(Prestataire).filter(Prestataire.id == presta_id).first()
    if not presta:
        raise HTTPException(status_code=404, detail="Prestataire introuvable")
    if not presta.iban_chiffre:
        return {"iban": None}
    return {"iban": decrypt_iban(presta.iban_chiffre)}
