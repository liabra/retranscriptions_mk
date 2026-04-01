import uuid
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models.prestataire import RolePrestaEnum


class PrestaCreate(BaseModel):
    nom: str
    role: RolePrestaEnum
    email: EmailStr
    telephone: Optional[str] = None
    disponible: bool = True
    iban: Optional[str] = None  # sera chiffré avant stockage
    grille_tarifaire_id: Optional[uuid.UUID] = None


class PrestaUpdate(BaseModel):
    nom: Optional[str] = None
    role: Optional[RolePrestaEnum] = None
    email: Optional[EmailStr] = None
    telephone: Optional[str] = None
    disponible: Optional[bool] = None
    iban: Optional[str] = None
    grille_tarifaire_id: Optional[uuid.UUID] = None
    actif: Optional[bool] = None


class PrestaOut(BaseModel):
    id: uuid.UUID
    nom: str
    role: RolePrestaEnum
    email: str
    telephone: Optional[str]
    disponible: bool
    charge_actuelle: int
    note_qualite: Decimal
    grille_tarifaire_id: Optional[uuid.UUID]
    actif: bool
    # IBAN non exposé dans la réponse standard

    model_config = {"from_attributes": True}
