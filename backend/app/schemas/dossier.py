import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel
from app.models.dossier import StatutDossierEnum, TypeInstanceEnum, NiveauConfidentialiteEnum


class DossierCreate(BaseModel):
    type_instance: TypeInstanceEnum
    client_id: uuid.UUID
    payeur_id: Optional[uuid.UUID] = None
    date_seance: Optional[date] = None
    date_reception_audio: datetime
    date_limite: Optional[date] = None
    duree_audio_minutes: Optional[int] = None
    niveau_confidentialite: NiveauConfidentialiteEnum = NiveauConfidentialiteEnum.STANDARD
    notes_internes: Optional[str] = None
    titre: Optional[str] = None


class DossierQualify(BaseModel):
    """Saisie des critères de tarification lors de la qualification."""
    duree_audio_minutes: Optional[int] = None
    date_limite: Optional[date] = None
    criteres_tarif: Dict[str, Any]
    # Critères attendus dans criteres_tarif:
    # urgence: bool
    # sans_prise_de_note: bool
    # prestation_speciale: bool
    # type_prestation_speciale: str | null
    # volume_estime_pages: float | null


class DossierTransition(BaseModel):
    statut: StatutDossierEnum


class DossierUpdate(BaseModel):
    titre: Optional[str] = None
    notes_internes: Optional[str] = None
    date_limite: Optional[date] = None
    niveau_confidentialite: Optional[NiveauConfidentialiteEnum] = None
    criteres_tarif: Optional[Dict[str, Any]] = None
    duree_audio_minutes: Optional[int] = None
    nombre_pages_final: Optional[Decimal] = None


class DossierOut(BaseModel):
    id: uuid.UUID
    reference: str
    titre: Optional[str]
    statut: StatutDossierEnum
    type_instance: TypeInstanceEnum
    date_seance: Optional[date]
    date_reception_audio: datetime
    date_limite: Optional[date]
    date_envoi_client: Optional[datetime]
    est_urgent: bool
    client_id: uuid.UUID
    payeur_id: Optional[uuid.UUID]
    duree_audio_minutes: Optional[int]
    nombre_pages_final: Optional[Decimal]
    criteres_tarif: Optional[Dict[str, Any]]
    calcul_tarifaire_id: Optional[uuid.UUID]
    niveau_confidentialite: NiveauConfidentialiteEnum
    notes_internes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DossierListItem(BaseModel):
    """Vue allégée pour les listes."""
    id: uuid.UUID
    reference: str
    titre: Optional[str]
    statut: StatutDossierEnum
    type_instance: TypeInstanceEnum
    date_limite: Optional[date]
    est_urgent: bool
    client_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
