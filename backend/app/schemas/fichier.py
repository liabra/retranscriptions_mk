import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
from app.models.fichier import TypeDocumentEnum, StatutFichierEnum


class FichierCreate(BaseModel):
    type_document: TypeDocumentEnum
    nom_fichier: str
    url_onedrive: str
    version: str = "1.0"
    commentaire: Optional[str] = None

    @field_validator("url_onedrive")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("L'URL doit commencer par https:// ou http://")
        return v


class FichierUpdate(BaseModel):
    nom_fichier: Optional[str] = None
    version: Optional[str] = None
    statut: Optional[StatutFichierEnum] = None
    commentaire: Optional[str] = None


class FichierOut(BaseModel):
    id: uuid.UUID
    dossier_id: uuid.UUID
    uploaded_by_id: Optional[uuid.UUID]
    type_document: TypeDocumentEnum
    nom_fichier: str
    url_onedrive: str
    version: str
    statut: StatutFichierEnum
    commentaire: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
