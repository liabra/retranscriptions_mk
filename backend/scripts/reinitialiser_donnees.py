"""
Réinitialisation COMPLÈTE des données (comptes, clients, dossiers, finances, journal…).

À n'utiliser que sur une base de démonstration : toutes les données sont définitivement supprimées,
puis les comptes internes initiaux et les grilles tarifaires sont recréés.

Double confirmation obligatoire :
    CONFIRMER_REINITIALISATION=SUPPRIMER-TOUT python scripts/reinitialiser_donnees.py --confirmer
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import app.db.base  # noqa: E402,F401
from sqlalchemy import text  # noqa: E402
from app.db.session import engine  # noqa: E402

TABLES = [
    "notifications", "encaissements", "demandes_correction", "livraisons", "stockage_fichiers", "audios",
    "graph_sync_state", "paiements_prestataires", "factures_clients", "incidents_qualite", "fichiers_dossier",
    "affectations", "journal_activites", "calculs_tarifaires", "dossiers", "users", "prestataires", "clients",
    "regles_tarifaires", "grilles_tarifaires",
]


def main() -> int:
    if "--confirmer" not in sys.argv or os.environ.get("CONFIRMER_REINITIALISATION") != "SUPPRIMER-TOUT":
        print(__doc__)
        return 1
    with engine.begin() as conn:
        existantes = [t for t in TABLES if conn.execute(text("SELECT to_regclass(:t)"), {"t": t}).scalar()]
        conn.execute(text("TRUNCATE " + ", ".join(existantes) + " RESTART IDENTITY CASCADE"))  # noms fixes, pas d'entrée utilisateur
    print(f"✓ {len(existantes)} tables vidées")
    from seed import seed
    from seed_grilles import seed_grilles
    from seed_parametres import seed_parametres
    seed()
    seed_grilles()
    seed_parametres()  # sans effet si la cliente a déjà paramétré ses délais
    return 0


if __name__ == "__main__":
    sys.exit(main())
