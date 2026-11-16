from app.models.journal import JournalActivite, TypeActionEnum
from app.models.user import RoleEnum
from tests.conftest import PASSWORD


def _login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", data={"username": email, "password": password})


def test_login_ok_et_journal_enregistre(client, f, db):
    u = f.user(RoleEnum.ADMINISTRATRICE, email="chef@exemple.fr")
    r = _login(client, "Chef@Exemple.fr")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "chef@exemple.fr"
    # B2 : la connexion est réellement journalisée
    entries = db.query(JournalActivite).filter(JournalActivite.utilisateur_id == u.id,
                                               JournalActivite.type_action == TypeActionEnum.AUTH).all()
    assert any(e.detail.get("action") == "login" for e in entries)


def test_login_mauvais_mot_de_passe(client, f, db):
    f.user(RoleEnum.ADMINISTRATRICE, email="x@exemple.fr")
    r = _login(client, "x@exemple.fr", "faux")
    assert r.status_code == 401
    assert r.json()["detail"] == "Email ou mot de passe incorrect"
    assert db.query(JournalActivite).filter(JournalActivite.type_action == TypeActionEnum.AUTH).count() == 1


def test_login_utilisateur_inconnu_meme_message(client):
    assert _login(client, "inconnu@exemple.fr").json()["detail"] == "Email ou mot de passe incorrect"


def test_anti_bruteforce(client, f):
    f.user(RoleEnum.ADMINISTRATRICE, email="cible@exemple.fr")
    for _ in range(5):
        assert _login(client, "cible@exemple.fr", "mauvais").status_code == 401
    assert _login(client, "cible@exemple.fr").status_code == 429


def test_sans_jeton_401(client):
    assert client.get("/api/v1/dossiers").status_code == 401
    assert client.get("/api/v1/dossiers", headers={"Authorization": "Bearer invalide"}).status_code == 401


def test_changement_mot_de_passe_impose(client, f, db):
    u = f.user(RoleEnum.ADMINISTRATRICE, must_change_password=True)
    h = f.headers(u)
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200
    assert client.get("/api/v1/dossiers", headers=h).status_code == 403
    r = client.post("/api/v1/auth/change-password", headers=h,
                    json={"ancien_mot_de_passe": PASSWORD, "nouveau_mot_de_passe": "court"})
    assert r.status_code == 400
    r = client.post("/api/v1/auth/change-password", headers=h,
                    json={"ancien_mot_de_passe": PASSWORD, "nouveau_mot_de_passe": "Nouveau-Secret-2026"})
    assert r.status_code == 200
    nouveau = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/dossiers", headers=nouveau).status_code == 200
    # l'ancien jeton est révoqué
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_desactivation_revoque_session(client, f, admin):
    cible = f.user(RoleEnum.COORDINATRICE)
    hc = f.headers(cible)
    assert client.get("/api/v1/dossiers", headers=hc).status_code == 200
    r = client.patch(f"/api/v1/auth/users/{cible.id}", headers=f.headers(admin), json={"actif": False})
    assert r.status_code == 200
    assert client.get("/api/v1/dossiers", headers=hc).status_code == 401


def test_gestion_utilisateurs_reservee_admin(client, f, coord, admin):
    assert client.get("/api/v1/auth/users", headers=f.headers(coord)).status_code == 403
    r = client.post("/api/v1/auth/users", headers=f.headers(admin),
                    json={"email": "nouvelle@exemple.fr", "nom": "Nouvelle", "role": "coordinatrice"})
    assert r.status_code == 201
    body = r.json()
    assert len(body["mot_de_passe_temporaire"]) >= 12
    assert body["user"]["must_change_password"] is True
    assert "hashed_password" not in body["user"]


def test_compte_retranscripteur_exige_une_fiche(client, f, admin):
    r = client.post("/api/v1/auth/users", headers=f.headers(admin),
                    json={"email": "r@exemple.fr", "nom": "R", "role": "retranscripteur"})
    assert r.status_code == 400


def test_role_correcteur_non_creable(client, f, admin):
    r = client.post("/api/v1/auth/users", headers=f.headers(admin),
                    json={"email": "c@exemple.fr", "nom": "C", "role": "correcteur"})
    assert r.status_code == 400


def test_admin_ne_peut_pas_se_retirer_ses_droits(client, f, admin):
    r = client.patch(f"/api/v1/auth/users/{admin.id}", headers=f.headers(admin), json={"actif": False})
    assert r.status_code == 400
