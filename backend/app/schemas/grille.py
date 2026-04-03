from typing import Optional, List
import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class RegleCreate(BaseModel):
    libelle: str
    type_regle: str
    condition_type: str = "toujours"
    condition_valeur: Optional[dict] = None
    mode_calcul: str
    valeur: Decimal
    unite: Optional[str] = None
    priorite: int = 100
    cumulable: bool = True
    plafond_montant: Optional[Decimal] = None
    actif: bool = True


class RegleUpdate(BaseModel):
    libelle: Optional[str] = None
    type_regle: Optional[str] = None
    condition_type: Optional[str] = None
    condition_valeur: Optional[dict] = None
    mode_calcul: Optional[str] = None
    valeur: Optional[Decimal] = None
    unite: Optional[str] = None
    priorite: Optional[int] = None
    cumulable: Optional[bool] = None
    plafond_montant: Optional[Decimal] = None
    actif: Optional[bool] = None


class RegleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    grille_id: uuid.UUID
    libelle: str
    type_regle: str
    condition_type: str
    condition_valeur: Optional[dict] = None
    mode_calcul: str
    valeur: Decimal
    unite: Optional[str] = None
    priorite: int
    cumulable: bool
    plafond_montant: Optional[Decimal] = None
    actif: bool


class GrilleCreate(BaseModel):
    nom: str
    type: str
    cible: str = "global"
    cible_id: Optional[uuid.UUID] = None
    version: str = "1.0"
    date_debut: date
    date_fin: Optional[date] = None
    description: Optional[str] = None


class GrilleUpdate(BaseModel):
    nom: Optional[str] = None
    version: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    active: Optional[bool] = None
    description: Optional[str] = None
    cible_id: Optional[uuid.UUID] = None


class GrilleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nom: str
    type: str
    cible: str
    cible_id: Optional[uuid.UUID] = None
    version: str
    date_debut: date
    date_fin: Optional[date] = None
    active: bool
    description: Optional[str] = None
    creee_par_id: Optional[uuid.UUID] = None
    date_creation: datetime


class GrilleWithReglesOut(GrilleOut):
    regles: List[RegleOut] = []
