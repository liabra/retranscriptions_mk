"""Cycle de production complet, machine d'états, versions et journal."""
import pytest

from app.models.journal import JournalActivite
from app.models.refonte import Notification
from tests.conftest import make_docx, docx_upload


def _dossier(client, mission):
    return client.get(f"/api/v1/dossiers/{mission['dossier_id']}", headers=mission["admin_h"]).json()


def test_cycle_complet_production(client, f, mission, coord, db):
    aid, d = mission["affectation_id"], mission["dossier_id"]
    ph, ah, ch = mission["presta_h"], mission["admin_h"], f.headers(coord)
    assert _dossier(client, mission)["statut_production"] == "attribue"

    # Le prestataire voit sa mission et commence
    missions = client.get("/api/v1/espace-prestataire/missions", headers=ph).json()
    assert missions[0]["etape"] == "a_commencer" and missions[0]["consignes"]
    assert client.post(f"/api/v1/espace-prestataire/missions/{aid}/commencer", headers=ph).json()["etape"] == "en_cours"

    # Dépôt v1 (non conforme : Arial 11) → accepté mais signalé
    r = client.post(f"/api/v1/espace-prestataire/missions/{aid}/livraisons", headers=ph,
                    files=docx_upload(make_docx(font="Arial", size=11)))
    assert r.status_code == 201, r.text
    assert r.json()["versions"][0]["statut_controle"] == "non_conforme"
    assert _dossier(client, mission)["statut_production"] == "livre"
    assert db.query(Notification).filter(Notification.user_id == coord.id, Notification.type == "pv_livre").count() == 1

    # Relecture par la coordinatrice → demande de correction
    assert client.post(f"/api/v1/dossiers/{d}/relecture/commencer", headers=ch).status_code == 200
    v1 = _dossier(client, mission)["livraisons"][0]
    r = client.post(f"/api/v1/dossiers/{d}/corrections", headers=ch,
                    json={"message": "Merci d'appliquer Comic Sans MS 12.", "livraison_id": v1["id"]})
    assert r.status_code == 201
    mis = client.get(f"/api/v1/espace-prestataire/missions/{aid}", headers=ph).json()
    assert mis["etape"] == "correction" and mis["corrections"][0]["message"].startswith("Merci")

    # Pendant la relecture le prestataire ne peut pas déposer ; après la demande, si
    r = client.post(f"/api/v1/espace-prestataire/missions/{aid}/livraisons", headers=ph,
                    files=docx_upload(make_docx()))
    assert r.status_code == 201
    assert [v["version"] for v in r.json()["versions"]] == [2, 1]
    assert r.json()["corrections"][0]["resolue_le"] is not None

    # Relecture, correction interne, comparaison, contrôle, validation
    client.post(f"/api/v1/dossiers/{d}/relecture/commencer", headers=ch)
    assert client.post(f"/api/v1/espace-prestataire/missions/{aid}/livraisons", headers=ph,
                       files=docx_upload(make_docx())).status_code == 409
    r = client.post(f"/api/v1/dossiers/{d}/livraisons", headers=ch, files=docx_upload(make_docx(paragraphs=4)))
    assert r.status_code == 201 and r.json()["type_depot"] == "correction_interne" and r.json()["version"] == 3
    livs = {l["version"]: l["id"] for l in _dossier(client, mission)["livraisons"]}
    cmp = client.get(f"/api/v1/livraisons/{livs[2]}/comparer/{livs[3]}", headers=ch).json()
    assert cmp["modifications"] >= 1
    fichier = client.get(f"/api/v1/livraisons/{livs[3]}/fichier", headers=ch)
    assert fichier.status_code == 200 and fichier.content[:2] == b"PK"

    assert client.post(f"/api/v1/dossiers/{d}/relecture/terminer", headers=ch).status_code == 200
    r = client.post(f"/api/v1/dossiers/{d}/valider", headers=ch,
                    json={"livraison_id": livs[3], "nombre_pages_final": "12"})
    assert r.status_code == 200, r.text
    assert r.json() == {"statut_production": "valide", "statut_facturation": "a_etablir"}
    assert client.get(f"/api/v1/espace-prestataire/missions?terminees=true", headers=ph).json()[0]["etape"] == "termine"
    # l'audio n'est plus accessible une fois la mission terminée
    assert client.get(f"/api/v1/espace-prestataire/missions/{aid}/audio", headers=ph).status_code == 403

    # Historique : chaque changement tracé avec son auteur
    entrees = db.query(JournalActivite).filter(JournalActivite.dossier_id == mission["dossier_id"]).all()
    assert len(entrees) >= 10 and all(e.utilisateur_id for e in entrees)


def test_validation_non_conforme_exige_derogation(client, f, mission, coord):
    aid, d, ch = mission["affectation_id"], mission["dossier_id"], f.headers(coord)
    client.post(f"/api/v1/espace-prestataire/missions/{aid}/livraisons", headers=mission["presta_h"],
                files=docx_upload(make_docx(font="Times New Roman")))
    client.post(f"/api/v1/dossiers/{d}/relecture/commencer", headers=ch)
    client.post(f"/api/v1/dossiers/{d}/relecture/terminer", headers=ch)
    lid = _dossier(client, mission)["livraisons"][0]["id"]
    assert client.post(f"/api/v1/dossiers/{d}/valider", headers=ch,
                       json={"livraison_id": lid, "nombre_pages_final": "5"}).status_code == 409
    assert client.post(f"/api/v1/dossiers/{d}/valider", headers=ch,
                       json={"livraison_id": lid, "nombre_pages_final": "5",
                             "derogation_motif": "Mise en forme refaite par nos soins"}).status_code == 200


@pytest.mark.parametrize("route,body", [
    ("relecture/terminer", None),
    ("valider", {"livraison_id": "00000000-0000-0000-0000-000000000000", "nombre_pages_final": "3"}),
    ("archiver", None),
])
def test_transitions_interdites(client, mission, route, body):
    r = client.post(f"/api/v1/dossiers/{mission['dossier_id']}/{route}", headers=mission["admin_h"], json=body)
    assert r.status_code in (404, 409)
    assert _dossier(client, mission)["statut_production"] == "attribue"


def test_attribution_exige_dossier_qualifie(client, f, admin):
    h = f.headers(admin)
    c = f.client_()
    p, _ = f.prestataire()
    d = client.post("/api/v1/dossiers", headers=h, json={"type_instance": "CSSCT", "client_id": str(c.id)}).json()
    assert d["statut_production"] == "a_qualifier"
    assert client.post(f"/api/v1/dossiers/{d['id']}/affectations", headers=h,
                       json={"prestataire_id": str(p.id)}).status_code == 409
    q = client.post(f"/api/v1/dossiers/{d['id']}/qualifier", headers=h,
                    json={"criteres_tarif": {"urgence": True}, "duree_audio_minutes": 300})
    assert q.json()["statut_production"] == "a_attribuer" and q.json()["est_urgent"] is True
    r = client.post(f"/api/v1/dossiers/{d['id']}/affectations", headers=h, json={"prestataire_id": str(p.id)})
    assert r.status_code == 201
    # double attribution refusée
    assert client.post(f"/api/v1/dossiers/{d['id']}/affectations", headers=h,
                       json={"prestataire_id": str(p.id)}).status_code == 409


def test_criteres_tarif_valides(client, f, admin):
    h = f.headers(admin)
    c = f.client_()
    r = client.post("/api/v1/dossiers", headers=h, json={
        "type_instance": "CE", "client_id": str(c.id), "criteres_tarif": {"urgence": "pas un booléen"}})
    assert r.status_code == 422


def test_prestataire_indisponible_confirmation(client, f, admin):
    h = f.headers(admin)
    c = f.client_()
    p, _ = f.prestataire(disponible=False)
    d = client.post("/api/v1/dossiers", headers=h, json={"type_instance": "CE", "client_id": str(c.id),
                                                         "criteres_tarif": {}, "qualifier": True}).json()
    assert client.post(f"/api/v1/dossiers/{d['id']}/affectations", headers=h,
                       json={"prestataire_id": str(p.id)}).status_code == 409
    assert client.post(f"/api/v1/dossiers/{d['id']}/affectations", headers=h,
                       json={"prestataire_id": str(p.id), "confirmer_indisponible": True}).status_code == 201


def test_blocage_et_deblocage(client, mission):
    d, h = mission["dossier_id"], mission["admin_h"]
    assert client.post(f"/api/v1/dossiers/{d}/bloquer", headers=h, json={"motif": "Audio inaudible"}).json()[
        "statut_production"] == "bloque"
    assert client.post(f"/api/v1/espace-prestataire/missions/{mission['affectation_id']}/livraisons",
                       headers=mission["presta_h"], files=docx_upload(make_docx())).status_code == 409
    assert client.post(f"/api/v1/dossiers/{d}/debloquer", headers=h).json()["statut_production"] == "attribue"


def test_suppression_logique_conserve_journal(client, f, admin, db):
    h = f.headers(admin)
    c = f.client_()
    d = client.post("/api/v1/dossiers", headers=h, json={"type_instance": "CE", "client_id": str(c.id)}).json()
    assert client.delete(f"/api/v1/dossiers/{d['id']}", headers=h).status_code == 204
    assert client.get(f"/api/v1/dossiers/{d['id']}", headers=h).status_code == 404
    assert db.query(JournalActivite).filter(JournalActivite.dossier_id == d["id"]).count() >= 2
    # la référence n'est pas réutilisée
    d2 = client.post("/api/v1/dossiers", headers=h, json={"type_instance": "CE", "client_id": str(c.id)}).json()
    assert d2["reference"] != d["reference"]


def test_suppression_impossible_apres_attribution(client, mission):
    assert client.delete(f"/api/v1/dossiers/{mission['dossier_id']}", headers=mission["admin_h"]).status_code == 409


def test_journal_immuable(db, mission):
    e = db.query(JournalActivite).first()
    e.detail = {"falsifie": True}
    with pytest.raises(RuntimeError):
        db.commit()
    db.rollback()
    with pytest.raises(RuntimeError):
        db.delete(db.query(JournalActivite).first())
        db.commit()
    db.rollback()


def test_prestataire_ne_modifie_pas_son_echeance(client, mission):
    r = client.patch(f"/api/v1/affectations/{mission['affectation_id']}", headers=mission["presta_h"],
                     json={"date_limite_rendu": "2099-01-01T00:00:00Z"})
    assert r.status_code == 403


def test_depot_refuse_si_pas_docx(client, mission):
    aid, ph = mission["affectation_id"], mission["presta_h"]
    for name, content in (("pv.docx", b"ceci n'est pas un document"), ("pv.pdf", b"%PDF-1.4"),
                          ("pv.doc", make_docx())):
        r = client.post(f"/api/v1/espace-prestataire/missions/{aid}/livraisons", headers=ph,
                        files={"file": (name, content, "application/octet-stream")})
        assert r.status_code == 400, name
    assert _dossier(client, mission)["livraisons"] == []
