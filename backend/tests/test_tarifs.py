"""Tarifs et majorations administrables : versions, publication datée, non-rétroactivité."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.journal import JournalActivite, TypeActionEnum
from app.models.pricing.calcul import CalculTarifaire
from app.models.pricing.grille import GrilleTarifaire, TypeGrilleEnum
from app.models.user import RoleEnum
from tests.conftest import make_docx, docx_upload

AUJ = date.today().isoformat()


@pytest.fixture
def grilles():
    from seed_grilles import seed_grilles
    seed_grilles()


@pytest.fixture
def h(f, admin):
    return f.headers(admin)


def famille(client, h, usage, nom):
    return next(x for x in client.get(f"/api/v1/tarifs/catalogue?usage={usage}", headers=h).json() if x["nom"].startswith(nom))


def simuler(client, h, **kw):
    body = {"nombre_pages": "15", "type_instance": "CE", **kw}
    r = client.post("/api/v1/tarifs/simuler", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_catalogue_bareme_initial_conserve(client, h, grilles):
    fam = famille(client, h, "client", "Tarif client A2C")
    assert fam["courante"]["statut"] == "en_vigueur"
    tr = fam["courante"]["tranches"]
    assert len(tr) == 11 and Decimal(tr[0]["montant"]) == 50 and tr[-1]["mode"] == "par_page"
    # l'ancienne référence 5 €/page reste dans l'historique de la même grille, désactivée
    assert any(v["statut"] == "desactivee" and v["nom"] == "Tarif client standard" for v in fam["versions"])
    fam_urg = famille(client, h, "majorations", "Majoration urgence")
    assert fam_urg["courante"] is None  # désactivée tant que la cliente n'a pas confirmé sa règle
    urg = fam_urg["versions"][0]
    assert urg["statut"] == "desactivee"
    # anciennes valeurs conservées à titre indicatif, sans effet
    assert urg["majoration"]["mode"] == "pourcentage" and Decimal(str(urg["majoration"]["valeur"])) == 30
    assert urg["conditions"] == {"case_cochee": True, "dossier_signale_urgent": True, "delai_max_jours": None}


def urgence_id(client, h):
    return famille(client, h, "majorations", "Majoration urgence")["versions"][0]["id"]


def test_simulateur_et_urgence_desactivee_par_defaut(client, h, grilles):
    s = simuler(client, h)
    assert Decimal(s["montant_client"]) == 100 and Decimal(s["montant_retranscripteur"]) == 100
    s = simuler(client, h, urgence=True)
    assert Decimal(s["montant_client"]) == 100 and s["majorations"] == []
    # la cliente confirme sa règle : nouvelle version publiée
    r = client.post(f"/api/v1/tarifs/grilles/{urgence_id(client, h)}/reviser", headers=h, json={
        "mode": "pourcentage", "valeur": "15", "applique_client": True, "applique_retranscripteur": True, "publier_le": AUJ})
    assert r.status_code == 201 and r.json()["statut"] == "en_vigueur"
    s = simuler(client, h, urgence=True)
    assert Decimal(s["montant_client"]) == 115 and Decimal(s["montant_retranscripteur"]) == 115


def test_brouillon_jamais_applique_puis_publication(client, h, grilles):
    r = client.post("/api/v1/tarifs/grilles", headers=h, json={
        "nom": "Tarif client 2027", "usage": "client", "application": "defaut",
        "tranches": [{"pages_min": 1, "mode": "forfait", "montant": 999}]})
    assert r.status_code == 201 and r.json()["statut"] == "brouillon"
    assert Decimal(simuler(client, h)["montant_client"]) == 100
    hier = (date.today() - timedelta(days=1)).isoformat()
    assert client.post(f"/api/v1/tarifs/grilles/{r.json()['id']}/publier", headers=h,
                       json={"date_debut": hier}).status_code == 400  # jamais dans le passé
    demain = (date.today() + timedelta(days=1)).isoformat()
    p = client.post(f"/api/v1/tarifs/grilles/{r.json()['id']}/publier", headers=h, json={"date_debut": demain})
    assert p.json()["statut"] == "programmee"
    assert Decimal(simuler(client, h)["montant_client"]) == 100
    assert Decimal(simuler(client, h, date_reference=demain)["montant_client"]) == 999


def test_version_publiee_non_modifiable_sur_place(client, h, grilles):
    fam = famille(client, h, "client", "Tarif client A2C")
    vid = fam["courante"]["id"]
    assert client.put(f"/api/v1/tarifs/grilles/{vid}", headers=h, json={"nom": "Autre nom"}).status_code == 409
    r = client.post(f"/api/v1/tarifs/grilles/{vid}/reviser", headers=h, json={
        "tranches": [{"pages_min": 1, "mode": "forfait", "montant": 60}, {"pages_min": 10, "mode": "forfait", "montant": 120}]})
    assert r.status_code == 201 and r.json()["brouillon"] and r.json()["famille_id"] == fam["famille_id"]
    assert r.json()["version"] != fam["courante"]["version"]
    # un seul brouillon à la fois
    assert client.post(f"/api/v1/tarifs/grilles/{vid}/reviser", headers=h, json={}).status_code == 409
    # l'original est intact
    assert Decimal(str(client.get(f"/api/v1/tarifs/grilles/{vid}", headers=h).json()["tranches"][0]["montant"])) == 50
    assert client.put(f"/api/v1/tarifs/grilles/{r.json()['id']}", headers=h, json={"nom": "Tarif client A2C 2027"}).status_code == 200
    assert client.delete(f"/api/v1/tarifs/grilles/{r.json()['id']}", headers=h).status_code == 204
    assert client.delete(f"/api/v1/tarifs/grilles/{vid}", headers=h).status_code == 409


@pytest.fixture
def valide(client, mission, grilles):
    aid, d, ah = mission["affectation_id"], mission["dossier_id"], mission["admin_h"]
    client.post(f"/api/v1/espace-prestataire/missions/{aid}/livraisons", headers=mission["presta_h"], files=docx_upload(make_docx()))
    client.post(f"/api/v1/dossiers/{d}/relecture/commencer", headers=ah)
    client.post(f"/api/v1/dossiers/{d}/relecture/terminer", headers=ah)
    lid = client.get(f"/api/v1/dossiers/{d}", headers=ah).json()["livraisons"][0]["id"]
    client.post(f"/api/v1/dossiers/{d}/valider", headers=ah, json={"livraison_id": lid, "nombre_pages_final": "15"})
    return mission


def test_non_retroactivite_calculs_factures_et_dossiers_recus(client, h, valide, db, f):
    d, ah = valide["dossier_id"], valide["admin_h"]
    calc = client.post(f"/api/v1/dossiers/{d}/calculer", headers=ah, json={}).json()
    client.post(f"/api/v1/calculs/{calc['id']}/valider", headers=ah)
    fac = client.post(f"/api/v1/dossiers/{d}/generer-facture", headers=ah, json={}).json()
    # copie intégrale des paramètres dans le calcul
    c = db.query(CalculTarifaire).filter(CalculTarifaire.id == calc["id"]).one()
    snap = next(v for v in c.grilles_version_snap.values() if v["type"] == "client")
    assert snap["version"] == "2026.1" and any(r["valeur"] == "100.0000" for r in snap["regles"])
    assert c.criteres_appliques["_tarification"]["date_reference"] == AUJ

    # Un dossier reçu hier, pas encore calculé
    d2 = client.post("/api/v1/dossiers", headers=ah, json={
        "type_instance": "CE", "client_id": str(valide["client"].id), "criteres_tarif": {},
        "date_reception_audio": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}).json()

    # La cliente double ses tarifs à partir d'aujourd'hui
    vid = famille(client, h, "client", "Tarif client A2C")["courante"]["id"]
    r = client.post(f"/api/v1/tarifs/grilles/{vid}/reviser", headers=h, json={
        "tranches": [{"pages_min": 1, "mode": "forfait", "montant": 200}], "publier_le": AUJ})
    assert r.status_code == 201 and r.json()["statut"] == "en_vigueur"
    ancienne = client.get(f"/api/v1/tarifs/grilles/{vid}", headers=h).json()
    assert ancienne["statut"] == "archivee" and ancienne["date_fin"] == (date.today() - timedelta(days=1)).isoformat()

    # Calcul et facture validés inchangés, recalcul interdit
    assert Decimal(client.get(f"/api/v1/calculs/{calc['id']}", headers=ah).json()["montant_client_final"]) == 100
    assert Decimal(client.get(f"/api/v1/factures/{fac['id']}", headers=ah).json()["montant_ttc"]) == 100
    assert client.post(f"/api/v1/dossiers/{d}/calculer", headers=ah, json={}).status_code == 409
    # Le dossier reçu hier garde l'ancien tarif ; un audio reçu aujourd'hui prend le nouveau
    assert Decimal(client.post(f"/api/v1/dossiers/{d2['id']}/calculer", headers=ah,
                               json={"nombre_pages": "15"}).json()["montant_client_final"]) == 100
    assert Decimal(simuler(client, h)["montant_client"]) == 200


def test_majoration_independante_client_et_retranscripteur(client, h, grilles):
    vid = urgence_id(client, h)
    r = client.post(f"/api/v1/tarifs/grilles/{vid}/reviser", headers=h, json={
        "mode": "montant", "valeur": "20", "applique_client": True, "applique_retranscripteur": False, "publier_le": AUJ})
    assert r.status_code == 201, r.text
    s = simuler(client, h, urgence=True)
    assert Decimal(s["montant_client"]) == 120 and Decimal(s["montant_retranscripteur"]) == 100
    # désactivation
    assert client.post(f"/api/v1/tarifs/grilles/{r.json()['id']}/desactiver", headers=h).status_code == 200
    assert Decimal(simuler(client, h, urgence=True)["montant_client"]) == 100
    # au moins une application obligatoire
    assert client.post(f"/api/v1/tarifs/grilles/{r.json()['id']}/reviser", headers=h, json={
        "applique_client": False, "applique_retranscripteur": False}).status_code == 400


def test_majoration_par_delai(client, h, grilles):
    vid = urgence_id(client, h)
    client.post(f"/api/v1/tarifs/grilles/{vid}/reviser", headers=h, json={
        "conditions": {"case_cochee": False, "dossier_signale_urgent": False, "delai_max_jours": 5}, "publier_le": AUJ})
    proche = (date.today() + timedelta(days=3)).isoformat()
    loin = (date.today() + timedelta(days=10)).isoformat()
    assert Decimal(simuler(client, h, date_limite=proche)["montant_client"]) == 130
    assert Decimal(simuler(client, h, date_limite=loin)["montant_client"]) == 100
    assert Decimal(simuler(client, h, urgence=True, date_limite=loin)["montant_client"]) == 100  # case ignorée


def test_nouvelle_majoration_sans_prise_de_notes(client, h, grilles):
    r = client.post("/api/v1/tarifs/majorations", headers=h, json={
        "type": "snp", "nom": "Sans prise de notes", "mode": "pourcentage", "valeur": "10",
        "applique_client": True, "applique_retranscripteur": False})
    assert r.status_code == 201
    client.post(f"/api/v1/tarifs/grilles/{r.json()['id']}/publier", headers=h, json={"date_debut": AUJ})
    s = simuler(client, h, sans_prise_de_note=True)
    assert Decimal(s["montant_client"]) == 110 and Decimal(s["montant_retranscripteur"]) == 100


def test_grilles_attribuees_et_par_instance(client, h, grilles, f, db):
    # Grille retranscripteur Togo : appliquée uniquement si attribuée sur la fiche
    p, _ = f.prestataire("Ama Togo")
    togo = famille(client, h, "retranscripteur", "Tarif retranscripteur Togo")["courante"]
    assert togo["application"] == "attribuee"
    assert Decimal(simuler(client, h, prestataire_id=str(p.id))["montant_retranscripteur"]) == 100
    client.patch(f"/api/v1/prestataires/{p.id}", headers=h, json={"grille_tarifaire_id": togo["id"]})
    assert Decimal(simuler(client, h, prestataire_id=str(p.id))["montant_retranscripteur"]) == 50

    # Grille client propre à un client
    c = f.client_("CSE Spécifique")
    g = client.post("/api/v1/tarifs/grilles", headers=h, json={
        "nom": "Tarif négocié", "usage": "client", "application": "attribuee",
        "tranches": [{"pages_min": 1, "mode": "par_page", "montant": 4}]}).json()
    client.post(f"/api/v1/tarifs/grilles/{g['id']}/publier", headers=h, json={"date_debut": AUJ})
    assert Decimal(simuler(client, h, client_id=str(c.id))["montant_client"]) == 100  # pas encore attribuée
    client.patch(f"/api/v1/clients/{c.id}", headers=h, json={"grille_tarifaire_id": g["id"]})
    assert Decimal(simuler(client, h, client_id=str(c.id))["montant_client"]) == 60

    # Grille par type d'instance
    gi = client.post("/api/v1/tarifs/grilles", headers=h, json={
        "nom": "Tarif CSSCT", "usage": "client", "application": "instance", "type_instance": "CSSCT",
        "tranches": [{"pages_min": 1, "mode": "forfait", "montant": 80}]}).json()
    client.post(f"/api/v1/tarifs/grilles/{gi['id']}/publier", headers=h, json={"date_debut": AUJ})
    assert Decimal(simuler(client, h, type_instance="CSSCT")["montant_client"]) == 80
    assert Decimal(simuler(client, h, type_instance="CE")["montant_client"]) == 100


def test_validation_des_tranches(client, h, grilles):
    base = {"nom": "T", "usage": "client"}
    for tranches in ([], [{"pages_min": 5, "mode": "forfait", "montant": 10}],
                     [{"pages_min": 1, "mode": "forfait", "montant": 10}, {"pages_min": 1, "mode": "forfait", "montant": 20}],
                     [{"pages_min": 1, "mode": "forfait", "montant": 0}]):
        assert client.post("/api/v1/tarifs/grilles", headers=h, json={**base, "tranches": tranches}).status_code == 422


def test_droits_tarifs(client, f, grilles):
    coord = f.headers(f.user(RoleEnum.COORDINATRICE))
    compta = f.headers(f.user(RoleEnum.COMPTABILITE))
    body = {"nom": "X", "usage": "client", "tranches": [{"pages_min": 1, "mode": "forfait", "montant": 10}]}
    assert client.get("/api/v1/tarifs/catalogue", headers=coord).status_code == 403
    assert client.get("/api/v1/tarifs/catalogue", headers=compta).status_code == 200
    assert client.post("/api/v1/tarifs/grilles", headers=compta, json=body).status_code == 403
    _, presta = f.prestataire()
    assert client.post("/api/v1/tarifs/simuler", headers=f.headers(presta), json={"nombre_pages": "3"}).status_code == 403


def test_modifications_historisees(client, h, grilles, db):
    vid = urgence_id(client, h)
    client.post(f"/api/v1/tarifs/grilles/{vid}/reviser", headers=h, json={"valeur": "25", "publier_le": AUJ})
    actions = [e.detail["action"] for e in db.query(JournalActivite).filter(
        JournalActivite.type_action == TypeActionEnum.CONFIG_GRILLE).all()]
    assert "nouvelle_version" in actions and "publication" in actions
    fam = famille(client, h, "majorations", "Majoration urgence")
    assert [v["statut"] for v in fam["versions"]][:2] == ["en_vigueur", "desactivee"]
    assert db.query(GrilleTarifaire).filter(GrilleTarifaire.type == TypeGrilleEnum.URGENCE).count() == 2


def test_attribution_tarif_reservee_au_droit_tarifs(client, f, grilles, h):
    coord = f.headers(f.user(RoleEnum.COORDINATRICE))  # clients.gerer mais pas tarifs.gerer
    c = f.client_()
    togo = famille(client, h, "retranscripteur", "Tarif retranscripteur Togo")["courante"]
    assert client.patch(f"/api/v1/clients/{c.id}", headers=coord, json={"grille_tarifaire_id": togo["id"]}).status_code == 403
    assert client.patch(f"/api/v1/clients/{c.id}", headers=coord, json={"telephone": "0102030405"}).status_code == 200
