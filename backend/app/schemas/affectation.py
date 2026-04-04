import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel
from app.models.affectation import RoleAffectationEnum, StatutAffectationEnum


class AffectationCreate(BaseModel):
    prestataire_id: uuid.UUID
    type_role: RoleAffectationEnum
    date_limite_rendu: Optional[datetime] = None
    commentaire: Optional[str] = None


class AffectationUpdate(BaseModel):
    statut: Optional[StatutAffectationEnum] = None
    date_limite_rendu: Optional[datetime] = None
    date_rendu_effectif: Optional[datetime] = None
    commentaire: Optional[str] = None


class AffectationOut(BaseModel):
    id: uuid.UUID
    dossier_id: uuid.UUID
    prestataire_id: uuid.UUID
    type_role: RoleAffectationEnum
    statut: StatutAffectationEnum
    date_attribution: datetime
    date_limite_rendu: Optional[datetime]
    date_rendu_effectif: Optional[datetime]
    montant_calcule: Optional[Decimal]
    commentaire: Optional[str]
    grille_snap: Optional[Dict[str, Any]]

    model_config = {"from_attributes": True}


class DossierMinimalOut(BaseModel):
    id: uuid.UUID
    reference: str
    statut: str
    titre: Optional[str]
    model_config = {"from_attributes": True}


class AffectationWithDossierOut(AffectationOut):
    dossier: DossierMinimalOut
