from typing import Optional, List, Any
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class CalculTrigger(BaseModel):
    nombre_pages: Decimal
    force_recalcul: bool = False


class CalculAjustement(BaseModel):
    ajustement_client: Decimal
    motif_ajustement_client: str


class CalculOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dossier_id: uuid.UUID
    version_calcul: int
    date_calcul: datetime
    nombre_pages: Decimal
    criteres_appliques: Optional[dict] = None
    regles_appliquees: Optional[List[Any]] = None
    montant_client_brut: Decimal
    ajustement_client: Decimal
    motif_ajustement_client: Optional[str] = None
    montant_client_final: Decimal
    montant_retranscripteur: Decimal
    montant_correcteur: Decimal
    montant_prestataires_total: Decimal
    marge_brute: Decimal
    grilles_version_snap: Optional[dict] = None
    statut: str
    valide_par_id: Optional[uuid.UUID] = None
    declenche_par_id: Optional[uuid.UUID] = None
