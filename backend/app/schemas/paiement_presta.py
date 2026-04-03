from typing import Optional
import uuid
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class PaiementPrestaUpdate(BaseModel):
    statut: Optional[str] = None  # a_payer, valide, paye
    date_virement: Optional[date] = None
    reference_virement: Optional[str] = None
    ajustement_manuel: Optional[Decimal] = None
    motif_ajustement: Optional[str] = None


class PaiementPrestaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    affectation_id: uuid.UUID
    dossier_id: uuid.UUID
    prestataire_id: uuid.UUID
    role_paye: str
    nombre_pages: Decimal
    detail_calcul: Optional[dict] = None
    montant_brut: Decimal
    ajustement_manuel: Decimal
    motif_ajustement: Optional[str] = None
    montant_final: Decimal
    statut: str
    date_virement: Optional[date] = None
    reference_virement: Optional[str] = None
