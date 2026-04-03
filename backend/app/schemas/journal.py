from typing import Optional, Any
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    timestamp: datetime
    dossier_id: Optional[uuid.UUID] = None
    utilisateur_id: Optional[uuid.UUID] = None
    type_action: str
    detail: Optional[Any] = None
    ip_source: Optional[str] = None
