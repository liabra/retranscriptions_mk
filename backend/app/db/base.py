from app.db.base_class import Base  # noqa — re-export for Alembic

# Import order matters: classes referenced in relationship("ClassName") strings
# must be registered in SQLAlchemy's mapper registry BEFORE the mapper that
# references them is configured. SQLAlchemy resolves string references lazily
# at first mapper initialization, but all models must be imported by then.

from app.models.user import User  # noqa — referenced by most models
from app.models.pricing.grille import GrilleTarifaire  # noqa — referenced by Client, Prestataire
from app.models.pricing.regle import RegleTarifaire  # noqa — references GrilleTarifaire
from app.models.client import Client  # noqa — references GrilleTarifaire
from app.models.prestataire import Prestataire  # noqa — references GrilleTarifaire
from app.models.pricing.calcul import CalculTarifaire  # noqa — references Dossier (post_update)
from app.models.dossier import Dossier  # noqa — references Client, Prestataire, CalculTarifaire
from app.models.affectation import Affectation  # noqa — references Dossier, Prestataire
from app.models.journal import JournalActivite  # noqa — references Dossier, User
from app.models.incident import IncidentQualite  # noqa — references Dossier, User, Prestataire
from app.models.facture import FactureClient  # noqa — references Dossier, Client, CalculTarifaire
from app.models.paiement import PaiementPrestataire  # noqa — references Affectation, Dossier, Prestataire
