"""Attribution assistée, notifications, alertes, détection Graph, tableau de bord."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.affectation import Affectation
from app.models.refonte import AudioSource, Notification, GraphSyncState
from app.models.user import RoleEnum
from app.services import onedrive
from app.services.alertes import executer_alertes
from app.services.graph_sync import run_sync


def test_suggestions_donnees_insuffisantes(client, f, admin):
    h = f.headers(admin)
    c = f.client_()
    dispo, _ = f.prestataire("Disponible")
    indispo, _ = f.prestataire("Indisponible", disponible=False)
    d = client.post("/api/v1/dossiers", headers=h, json={"type_instance": "CE", "client_id": str(c.id),
                                                         "criteres_tarif": {}, "qualifier": True}).json()
    r = client.get(f"/api/v1/dossiers/{d['id']}/suggestions", headers=h).json()
    noms = [s["nom"] for s in r["suggestions"]]
    assert noms.index("Disponible") < noms.index("Indisponible")
    s = r["suggestions"][0]
    assert s["fiabilite_donnees"] == "insuffisante"
    assert any("Données insuffisantes" in a for a in s["alertes"])
    assert s["indicateurs"]["qualite"] is None and s["indicateurs"]["respect_delais"] is None  # rien d'inventé
    # aucune attribution automatique
    assert client.get(f"/api/v1/dossiers/{d['id']}", headers=h).json()["statut_production"] == "a_attribuer"


def test_suggestions_charge_et_specialite(client, f, admin, mission):
    h = mission["admin_h"]
    specialiste, _ = f.prestataire("Spécialiste", specialites=["CE"])
    d = client.post("/api/v1/dossiers", headers=h, json={"type_instance": "CE", "client_id": str(mission["client"].id),
                                                         "criteres_tarif": {}, "qualifier": True}).json()
    sugg = {s["nom"]: s for s in client.get(f"/api/v1/dossiers/{d['id']}/suggestions", headers=h).json()["suggestions"]}
    assert sugg["Retranscripteur"]["charge_actuelle"] == 1
    assert sugg["Spécialiste"]["rang"] < sugg["Retranscripteur"]["rang"]


def test_notification_attribution_sans_email_simule(db, mission):
    n = db.query(Notification).filter(Notification.user_id == mission["presta_user"].id).one()
    assert n.type == "mission_attribuee"
    assert n.email_statut == "non_configure"  # Brevo absent : jamais « envoye »


def test_notifications_api(client, mission):
    h = mission["presta_h"]
    r = client.get("/api/v1/notifications", headers=h).json()
    assert r["non_lues"] == 1 and r["email_configure"] is False
    nid = r["items"][0]["id"]
    assert client.post(f"/api/v1/notifications/{nid}/lu", headers=h).json()["lu"] is True
    # impossible de lire la notification d'un autre utilisateur
    assert client.post(f"/api/v1/notifications/{nid}/lu", headers=mission["admin_h"]).status_code == 404


def test_alertes_retard_dedoublonnees(db, mission):
    aff = db.query(Affectation).one()
    aff.date_limite_rendu = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    assert executer_alertes(db)["retards"] == 1
    executer_alertes(db)
    assert db.query(Notification).filter(Notification.user_id == mission["presta_user"].id,
                                         Notification.type == "retard").count() == 1


def test_alerte_echeance_proche(db, mission, parametres):
    aff = db.query(Affectation).one()
    aff.date_limite_rendu = datetime.now(timezone.utc) + timedelta(hours=20)
    db.commit()
    assert executer_alertes(db)["echeances_proches"] == 1


def test_dashboard_compteurs_reels(client, f, mission, admin):
    r = client.get("/api/v1/dashboard", headers=mission["admin_h"]).json()
    assert r["production"]["en_cours"] == 1 and r["production"]["a_attribuer"] == 0
    assert r["finance"]["factures_a_etablir"] == 0
    coord = f.user(RoleEnum.COORDINATRICE)
    rc = client.get("/api/v1/dashboard", headers=f.headers(coord)).json()
    assert rc["finance"] is None  # pas de finance par défaut pour la coordinatrice
    lst = client.get("/api/v1/dossiers?production=attribue,en_cours", headers=mission["admin_h"]).json()
    assert lst["total"] == 1 and lst["items"][0]["retranscripteur"]["nom"] == "Retranscripteur"


# ── Détection Microsoft Graph (client simulé : aucune connexion réelle) ─────
class FakeGraph:
    def __init__(self, items, fail=False):
        self.items, self.fail, self.links = items, fail, []

    def delta(self, folder, link):
        self.links.append(link)
        if self.fail:
            raise onedrive.GraphError("Microsoft Graph indisponible")
        return self.items, "https://graph.microsoft.com/v1.0/delta?token=2"


ITEMS = [
    {"id": "A1", "name": "CSE 12-11.mp3", "size": 1000, "file": {"mimeType": "audio/mpeg"},
     "parentReference": {"driveId": "D1"}, "eTag": "e1", "audio": {"duration": 3_600_000}},
    {"id": "F1", "name": "Sous-dossier", "folder": {}, "parentReference": {"driveId": "D1"}},
    {"id": "X1", "name": "notes.txt", "file": {"mimeType": "text/plain"}, "parentReference": {"driveId": "D1"}},
]


def test_detection_graph_sans_doublon(db, f, admin):
    state = run_sync(db, FakeGraph(ITEMS))
    assert state.nouveaux_detectes == 1 and state.delta_link
    a = db.query(AudioSource).one()
    assert (a.origine, a.statut, a.duree_minutes, a.dossier_id) == ("detection_graph", "a_traiter", 60, None)
    fake = FakeGraph(ITEMS)
    run_sync(db, fake)
    assert db.query(AudioSource).count() == 1  # pas de doublon
    assert fake.links == ["https://graph.microsoft.com/v1.0/delta?token=2"]  # reprise au dernier point
    assert db.query(Notification).filter(Notification.user_id == admin.id, Notification.type == "nouvel_audio").count() == 1


def test_detection_graph_erreur_ne_perd_pas_la_position(db):
    run_sync(db, FakeGraph(ITEMS))
    state = run_sync(db, FakeGraph([], fail=True))
    assert state.echecs_consecutifs == 1 and "indisponible" in state.derniere_erreur
    assert db.query(GraphSyncState).one().delta_link == "https://graph.microsoft.com/v1.0/delta?token=2"


def test_graph_non_configure_explicite(client, f, admin):
    h = f.headers(admin)
    assert client.get("/api/v1/audios-synchronisation", headers=h).json()["onedrive_configure"] is False
    assert client.post("/api/v1/audios-synchronisation", headers=h).status_code == 503
    with pytest.raises(onedrive.GraphNotConfigured):
        onedrive.GraphClient()


@pytest.mark.parametrize("url,ok", [
    ("https://contoso-my.sharepoint.com/:u:/g/personal/x", True),
    ("https://1drv.ms/u/s!abc", True),
    ("https://onedrive.live.com/?id=1", True),
    ("http://1drv.ms/u/s!abc", False),
    ("https://1drv.ms.attaquant.fr/x", False),
    ("file:///etc/passwd", False),
])
def test_validation_liens_onedrive(url, ok):
    assert onedrive.lien_onedrive_valide(url) is ok


def test_audio_signature_verifiee(client, f, admin):
    r = client.post("/api/v1/audios/fichier", headers=f.headers(admin),
                    files={"file": ("faux.mp3", b"<html>pas un audio</html>", "audio/mpeg")})
    assert r.status_code == 400


def test_alerte_echeance_proche_non_parametree(db, mission):
    aff = db.query(Affectation).one()
    aff.date_limite_rendu = datetime.now(timezone.utc) + timedelta(hours=20)
    db.commit()
    assert executer_alertes(db)["echeances_proches"] == 0  # aucun seuil inventé
