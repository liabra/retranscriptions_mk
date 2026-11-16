"""Migration 0005 appliquée sur une base contenant des données de l'ancien modèle."""
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def base_vierge():
    url = make_url(os.environ["DATABASE_URL"])
    name = f"a2c_migr_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    target = url.set(database=name).render_as_string(hide_password=False)
    yield target
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def _cfg(url):
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "alembic"))
    return cfg


def _upgrade(url, rev):
    old = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(_cfg(url), rev)
    finally:
        os.environ["DATABASE_URL"] = old


def test_reprise_donnees_anciennes(base_vierge):
    _upgrade(base_vierge, "0004")
    eng = create_engine(base_vierge)
    ids = {k: uuid.uuid4() for k in ("u_presta", "u_client", "presta", "client", "d1", "d2", "d3")}
    with eng.begin() as c:
        c.execute(text("INSERT INTO clients (id, nom, type, email_contact, actif) VALUES (:id,'CSE','CE','cse@x.fr',true)"),
                  {"id": ids["client"]})
        c.execute(text("INSERT INTO prestataires (id, nom, role, email, disponible, charge_actuelle, note_qualite, actif) "
                       "VALUES (:id,'P','RETRANSCRIPTEUR','p@x.fr',true,0,1,true)"), {"id": ids["presta"]})
        for key, email, role in (("u_presta", "P@x.fr", "RETRANSCRIPTEUR"), ("u_client", "cse@x.fr", "CLIENT")):
            c.execute(text("INSERT INTO users (id,email,nom,hashed_password,role,actif) VALUES (:id,:e,'n','h',:r,true)"),
                      {"id": ids[key], "e": email, "r": role})
        for key, statut in (("d1", "EN_RETRANSCRIPTION"), ("d2", "FACTURE"), ("d3", "PRESTATAIRES_PAYES")):
            c.execute(text("INSERT INTO dossiers (id, reference, statut, type_instance, date_reception_audio, est_urgent, "
                           "urgence_forcee, client_id, niveau_confidentialite) VALUES (:id,:ref,:s,'CE',now(),false,false,"
                           ":c,'STANDARD')"), {"id": ids[key], "ref": key, "s": statut, "c": ids["client"]})
        for gid, t in ((uuid.uuid4(), "URGENCE"), (uuid.uuid4(), "SNP")):
            c.execute(text("INSERT INTO grilles_tarifaires (id, nom, type, cible, version, date_debut, active) "
                           "VALUES (:id, :t, :t, 'GLOBAL', '1.0', '2025-01-01', true)"), {"id": gid, "t": t})
    _upgrade(base_vierge, "head")
    with eng.connect() as c:
        g = {r.type: r for r in c.execute(text("SELECT * FROM grilles_tarifaires"))}
        assert g["URGENCE"].famille_id == g["URGENCE"].id and g["URGENCE"].brouillon is False
        assert g["URGENCE"].applique_client and g["URGENCE"].applique_retranscripteur  # comportement actuel conservé
        assert g["URGENCE"].conditions["case_cochee"] is True
        assert g["URGENCE"].active is False  # 0007 : urgence désactivée tant que non confirmée
        assert g["SNP"].applique_client and not g["SNP"].applique_retranscripteur
        rows = dict(c.execute(text("SELECT reference, statut_production || '/' || statut_facturation FROM dossiers")).all())
        assert rows == {"d1": "en_cours/non_applicable", "d2": "valide/emise", "d3": "valide/reglee"}
        # l'ancien statut est conservé (aucune perte)
        assert c.execute(text("SELECT statut FROM dossiers WHERE reference='d2'")).scalar() == "FACTURE"
        assert c.execute(text("SELECT prestataire_id FROM users WHERE id=:i"), {"i": ids["u_presta"]}).scalar() == ids["presta"]
        assert c.execute(text("SELECT client_id FROM users WHERE id=:i"), {"i": ids["u_client"]}).scalar() == ids["client"]
    eng.dispose()


def test_0004_avec_enum_natif(base_vierge):
    """Schéma créé autrefois par create_all : le type roleenum existe."""
    eng = create_engine(base_vierge)
    with eng.begin() as c:
        c.execute(text("CREATE TYPE roleenum AS ENUM ('ADMINISTRATRICE')"))
    _upgrade(base_vierge, "head")
    with eng.connect() as c:
        valeurs = {r[0] for r in c.execute(text("SELECT unnest(enum_range(NULL::roleenum))::text"))}
    assert {"CLIENT", "client"} <= valeurs
    eng.dispose()
