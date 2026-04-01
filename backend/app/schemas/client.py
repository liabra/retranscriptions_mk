import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models.client import TypeClientEnum


class ClientCreate(BaseModel):
    nom: str
    type: TypeClientEnum
    entreprise_mere: Optional[str] = None
    contact_principal: Optional[str] = None
    email_contact: Optional[EmailStr] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    conditions_paiement: Optional[str] = None
    grille_tarifaire_id: Optional[uuid.UUID] = None


class ClientUpdate(BaseModel):
    nom: Optional[str] = None
    type: Optional[TypeClientEnum] = None
    entreprise_mere: Optional[str] = None
    contact_principal: Optional[str] = None
    email_contact: Optional[EmailStr] = None
    telephone: Optional[str] = None
    adresse: Optional[str] = None
    conditions_paiement: Optional[str] = None
    grille_tarifaire_id: Optional[uuid.UUID] = None
    actif: Optional[bool] = None


class ClientOut(BaseModel):
    id: uuid.UUID
    nom: str
    type: TypeClientEnum
    entreprise_mere: Optional[str]
    contact_principal: Optional[str]
    email_contact: Optional[str]
    telephone: Optional[str]
    conditions_paiement: Optional[str]
    grille_tarifaire_id: Optional[uuid.UUID]
    actif: bool

    model_config = {"from_attributes": True}
