from app.db.base_class import Base  # noqa — re-export for Alembic

# Import all models here so Alembic can detect them
from app.models.user import User  # noqa
from app.models.client import Client  # noqa
from app.models.prestataire import Prestataire  # noqa
from app.models.dossier import Dossier  # noqa
from app.models.affectation import Affectation  # noqa
from app.models.journal import JournalActivite  # noqa
from app.models.incident import IncidentQualite  # noqa
from app.models.facture import FactureClient  # noqa
from app.models.paiement import PaiementPrestataire  # noqa
from app.models.pricing.grille import GrilleTarifaire  # noqa
from app.models.pricing.regle import RegleTarifaire  # noqa
from app.models.pricing.calcul import CalculTarifaire  # noqa
