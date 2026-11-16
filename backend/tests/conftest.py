"""
Socle de tests — PostgreSQL réel.

- TEST_DATABASE_URL fourni (CI) : utilisé tel quel (base dédiée, vidée entre les tests).
- Sinon : un serveur PostgreSQL local est démarré via `pgserver` (dépendance de dev).
Le schéma est créé par les migrations Alembic (elles sont donc testées à chaque exécution).
"""
import io
import os
import secrets
import sys
import tempfile
import uuid

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_TMP = tempfile.mkdtemp(prefix="a2c-tests-")


def _database_url() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    import pgserver
    srv = pgserver.get_server(os.path.join(_TMP, "pg"), cleanup_mode="stop")
    name = f"a2c_test_{os.getpid()}"
    srv.psql(f"CREATE DATABASE {name};")
    return srv.get_uri(name)


os.environ.update({
    "DATABASE_URL": _database_url(),
    "SECRET_KEY": secrets.token_hex(32),
    "ENCRYPTION_KEY": __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode(),
    "APP_ENV": "test",
    "DEBUG": "false",
    "AUDIO_STORAGE_BACKEND": "local",
    "LOCAL_STORAGE_DIR": os.path.join(_TMP, "stockage"),
    "PV_STORAGE_BACKEND": "database",
    "ONEDRIVE_TENANT_ID": "", "ONEDRIVE_CLIENT_ID": "", "ONEDRIVE_CLIENT_SECRET": "", "ONEDRIVE_DRIVE_ID": "",
    "BREVO_API_KEY": "", "BREVO_SENDER_EMAIL": "",
    "ENABLE_SCHEDULER": "false",
})

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

_cfg = Config(os.path.join(ROOT, "alembic.ini"))
_cfg.set_main_option("script_location", os.path.join(ROOT, "alembic"))
command.upgrade(_cfg, "head")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.db.base  # noqa: E402,F401
from app.core.security import hash_password, create_access_token  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.client import Client, TypeClientEnum  # noqa: E402
from app.models.prestataire import Prestataire, RolePrestaEnum  # noqa: E402
from app.models.user import User, RoleEnum  # noqa: E402

PASSWORD = "Mot-De-Passe-Test-2026"
_HASH = hash_password(PASSWORD)


@pytest.fixture(autouse=True)
def _clean_db():
    yield
    with engine.begin() as conn:
        tables = [r[0] for r in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"))]
        conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " CASCADE"))
    from app.api.v1.auth import limiter
    limiter._hits.clear()


@pytest.fixture
def parametres():
    """Configuration initiale des délais et paramètres (vidée entre les tests)."""
    from seed_parametres import seed_parametres
    seed_parametres()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    return TestClient(app)


class Factory:
    def __init__(self, db):
        self.db = db

    def user(self, role: RoleEnum, **kw) -> User:
        u = User(email=kw.pop("email", f"{role.value}-{uuid.uuid4().hex[:6]}@exemple.fr"),
                 nom=kw.pop("nom", role.value.capitalize()), hashed_password=_HASH, role=role, **kw)
        self.db.add(u)
        self.db.commit()
        return u

    def headers(self, user: User) -> dict:
        self.db.refresh(user)
        return {"Authorization": f"Bearer {create_access_token(user.id, user.token_version or 0)}"}

    def client_(self, nom="CSE Exemple") -> Client:
        c = Client(nom=nom, type=TypeClientEnum.CE, email_contact=f"{uuid.uuid4().hex[:6]}@client.fr")
        self.db.add(c)
        self.db.commit()
        return c

    def prestataire(self, nom="Retranscripteur", **kw):
        p = Prestataire(nom=nom, role=RolePrestaEnum.RETRANSCRIPTEUR,
                        email=f"{uuid.uuid4().hex[:6]}@presta.fr", **kw)
        self.db.add(p)
        self.db.commit()
        u = self.user(RoleEnum.RETRANSCRIPTEUR, email=p.email, nom=nom, prestataire_id=p.id)
        return p, u


@pytest.fixture
def f(db):
    return Factory(db)


@pytest.fixture
def admin(f):
    return f.user(RoleEnum.ADMINISTRATRICE)


@pytest.fixture
def coord(f):
    return f.user(RoleEnum.COORDINATRICE)


# ── Documents de test ──────────────────────────────────────────────────────
def make_docx(font="Comic Sans MS", size=12, paragraphs=3, style_level=True) -> bytes:
    import docx
    from docx.shared import Pt
    d = docx.Document()
    if style_level:
        d.styles["Normal"].font.name = font
        d.styles["Normal"].font.size = Pt(size)
        for i in range(paragraphs):
            d.add_paragraph(f"Paragraphe {i + 1} : intervention du secrétaire du CSE.")
    else:
        for i in range(paragraphs):
            run = d.add_paragraph().add_run(f"Paragraphe {i + 1} du procès-verbal.")
            run.font.name = font
            run.font.size = Pt(size)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


FAKE_MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 2048


def docx_upload(content: bytes, name="PV.docx"):
    return {"file": (name, content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}


@pytest.fixture
def mission(client, f, admin, db):
    """Dossier qualifié, audio associé, attribué à un retranscripteur."""
    h = f.headers(admin)
    c = f.client_()
    presta, presta_user = f.prestataire()
    r = client.post("/api/v1/audios/fichier", headers=h, files={"file": ("seance.mp3", FAKE_MP3, "audio/mpeg")},
                    data={"client_id": str(c.id), "duree_minutes": "45"})
    assert r.status_code == 201, r.text
    audio_id = r.json()["id"]
    r = client.post("/api/v1/dossiers", headers=h, json={
        "type_instance": "CE", "client_id": str(c.id), "titre": "Séance plénière", "audio_id": audio_id,
        "criteres_tarif": {"urgence": False}, "qualifier": True,
    })
    assert r.status_code == 201, r.text
    dossier_id = r.json()["id"]
    r = client.post(f"/api/v1/dossiers/{dossier_id}/affectations", headers=h,
                    json={"prestataire_id": str(presta.id), "commentaire": "Merci de respecter le modèle."})
    assert r.status_code == 201, r.text
    return {"dossier_id": dossier_id, "affectation_id": r.json()["id"], "audio_id": audio_id,
            "client": c, "presta": presta, "presta_user": presta_user, "admin_h": h,
            "presta_h": f.headers(presta_user)}
