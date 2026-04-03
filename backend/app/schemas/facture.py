from typing import Optional
import uuid
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class FactureGenerate(BaseModel):
    tva_applicable: bool = False
    taux_tva: Decimal = Decimal("20.00")
    date_echeance: Optional[date] = None


class FacturePaiementUpdate(BaseModel):
    statut_paiement: str  # non_payee, partiellement, soldee


class FactureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    numero_facture: str
    dossier_id: uuid.UUID
    payeur_id: uuid.UUID
    calcul_tarifaire_id: uuid.UUID
    montant_ht: Decimal
    tva_applicable: bool
    taux_tva: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal
    date_emission: date
    date_echeance: Optional[date] = None
    statut_paiement: str
