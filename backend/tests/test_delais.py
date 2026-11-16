"""Délais de réalisation administrables : échéance = réception de l'audio + délai paramétré."""
from datetime import date, datetime, timedelta, timezone

from app.models.affectation import Affectation
from app.models.journal import JournalActivite, TypeActionEnum
from app.models.user import RoleEnum
from app.services.delais import ajouter_jours


def _creer(client, h, c, duree=None, reception=None, **kw):
    body = {"type_instance": "CE", "client_id": str(c.id), "duree_audio_minutes": duree, **kw}
    if reception:
        body["date_reception_audio"] = datetime.combine(reception, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    r = client.post("/api/v1/dossiers", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_sans_parametrage_aucune_echeance_inventee(client, f, admin):
    h = f.headers(admin)
    d = _creer(client, h, f.client_(), duree=45)
    assert d["date_limite"] is None and d["echeance_mode"] == "calculee"
    assert d["echeance_detail"]["regle"] is None and d["est_urgent"] is False


def test_configuration_initiale_depuis_reception(client, f, admin, parametres):
    h, c = f.headers(admin), f.client_()
    reception = date.today() - timedelta(days=3)
    for duree, jours in ((45, 7), (60, 7), (61, 18), (240, 18), (300, 25)):
        d = _creer(client, h, c, duree=duree, reception=reception)
        assert d["date_limite"] == (reception + timedelta(days=jours)).isoformat(), duree
        assert d["echeance_detail"]["delai_jours"] == jours
    # durée inconnue : aucune règle ne correspond (pas de délai deviné)
    assert _creer(client, h, c, duree=None)["date_limite"] is None


def test_regles_administrables_priorite_et_conditions(client, f, admin, parametres):
    h, c = f.headers(admin), f.client_()
    r = client.post("/api/v1/parametres/delais/regles", headers=h, json={
        "libelle": "CSSCT urgente", "priorite": 1, "type_instance": "CSSCT", "urgence": True, "delai_jours": 3})
    assert r.status_code == 201
    regle = r.json()
    recu = date.today()
    d = _creer(client, h, c, duree=45, reception=recu, type_instance="CSSCT", criteres_tarif={"urgence": True})
    assert d["date_limite"] == (recu + timedelta(days=3)).isoformat() and d["echeance_detail"]["regle"] == "CSSCT urgente"
    d2 = _creer(client, h, c, duree=45, reception=recu, type_instance="CSSCT")  # non urgente → règle générale
    assert d2["date_limite"] == (recu + timedelta(days=7)).isoformat()
    # jours ouvrés
    client.put(f"/api/v1/parametres/delais/regles/{regle['id']}", headers=h, json={**{k: regle[k] for k in (
        "libelle", "priorite", "type_instance", "urgence")}, "delai_jours": 3, "type_jours": "ouvres"})
    s = client.post("/api/v1/parametres/delais/simuler", headers=h, json={
        "date_reception": "2026-11-20", "type_instance": "CSSCT", "duree_minutes": 45, "urgence": True}).json()
    assert s["echeance"] == "2026-11-25"  # vendredi + 3 jours ouvrés = mercredi
    assert ajouter_jours(date(2026, 11, 20), 1, "ouvres") == date(2026, 11, 23)


def test_modification_des_delais_sans_effet_retroactif(client, f, mission, parametres, db):
    h = mission["admin_h"]
    avant = client.get(f"/api/v1/dossiers/{mission['dossier_id']}", headers=h).json()["date_limite"]
    # la mission (fixture) a été créée avant le paramétrage : on fixe une échéance calculée puis on change les règles
    regles = client.get("/api/v1/parametres/delais", headers=h).json()["regles"]
    for r in regles:
        client.put(f"/api/v1/parametres/delais/regles/{r['id']}", headers=h, json={
            **{k: r[k] for k in ("libelle", "priorite", "duree_min_minutes", "duree_max_minutes")}, "delai_jours": 60})
    assert client.get(f"/api/v1/dossiers/{mission['dossier_id']}", headers=h).json()["date_limite"] == avant
    # un nouveau dossier utilise les nouvelles règles
    d = _creer(client, h, mission["client"], duree=45, reception=date.today())
    assert d["date_limite"] == (date.today() + timedelta(days=60)).isoformat()
    assert db.query(JournalActivite).filter(JournalActivite.type_action == TypeActionEnum.CONFIG_GRILLE).count() == 3


def test_echeance_manuelle_puis_recalculee(client, f, admin, parametres):
    h, c = f.headers(admin), f.client_()
    d = _creer(client, h, c, duree=45, date_limite="2027-03-01")
    assert d["echeance_mode"] == "manuelle" and d["date_limite"] == "2027-03-01"
    r = client.post(f"/api/v1/dossiers/{d['id']}/echeance/recalculer", headers=h).json()
    assert r["echeance_mode"] == "calculee" and r["date_limite"] == (date.today() + timedelta(days=7)).isoformat()
    # la qualification recalcule tant que le dossier n'est pas attribué (durée corrigée)
    q = client.post(f"/api/v1/dossiers/{d['id']}/qualifier", headers=h,
                    json={"criteres_tarif": {}, "duree_audio_minutes": 300}).json()
    assert q["date_limite"] == (date.today() + timedelta(days=25)).isoformat()


def test_parametres_generaux(client, f, admin, parametres, db):
    h, c = f.headers(admin), f.client_()
    p, _ = f.prestataire()
    # marge de relecture : le retranscripteur rend 2 jours avant l'échéance client
    client.put("/api/v1/parametres/generaux", headers=h, json={"valeurs": {"marge_relecture_jours": 2}})
    d = _creer(client, h, c, duree=45, reception=date.today(), criteres_tarif={}, qualifier=True)
    client.post(f"/api/v1/dossiers/{d['id']}/affectations", headers=h, json={"prestataire_id": str(p.id)})
    aff = db.query(Affectation).one()
    assert aff.date_limite_rendu.date() == date.today() + timedelta(days=5)
    # seuil d'urgence : désactivé → aucun dossier signalé urgent automatiquement
    assert _creer(client, h, c, date_limite=(date.today() + timedelta(days=1)).isoformat())["est_urgent"] is True
    client.put("/api/v1/parametres/generaux", headers=h, json={"valeurs": {"seuil_urgence_jours": None}})
    assert _creer(client, h, c, date_limite=(date.today() + timedelta(days=1)).isoformat())["est_urgent"] is False
    assert client.put("/api/v1/parametres/generaux", headers=h, json={"valeurs": {"inconnu": 3}}).status_code == 422


def test_droits_delais(client, f, parametres):
    coord = f.headers(f.user(RoleEnum.COORDINATRICE))
    assert client.get("/api/v1/parametres/delais", headers=coord).status_code == 200
    assert client.post("/api/v1/parametres/delais/regles", headers=coord,
                       json={"libelle": "X", "delai_jours": 3}).status_code == 403
    _, presta = f.prestataire()
    assert client.get("/api/v1/parametres/delais", headers=f.headers(presta)).status_code == 403


def test_amorcage_ne_reecrit_pas_les_choix(client, f, admin, parametres):
    from seed_parametres import seed_parametres
    h = f.headers(admin)
    for r in client.get("/api/v1/parametres/delais", headers=h).json()["regles"]:
        client.delete(f"/api/v1/parametres/delais/regles/{r['id']}", headers=h)
    seed_parametres()  # redémarrage du serveur
    assert client.get("/api/v1/parametres/delais", headers=h).json()["regles"] == []


def _historique(db, dossier_id, action):
    return [e for e in db.query(JournalActivite).filter(JournalActivite.dossier_id == dossier_id)
            .order_by(JournalActivite.timestamp).all() if (e.detail or {}).get("action") == action]


def _modifier_regles(client, h, jours):
    for r in client.get("/api/v1/parametres/delais", headers=h).json()["regles"]:
        client.put(f"/api/v1/parametres/delais/regles/{r['id']}", headers=h, json={
            **{k: r[k] for k in ("libelle", "priorite", "duree_min_minutes", "duree_max_minutes")}, "delai_jours": jours})


def test_cycle_de_vie_echeance(client, f, admin, parametres, db):
    h, c = f.headers(admin), f.client_()
    p, _ = f.prestataire()
    auj = date.today()
    j = lambda n: (auj + timedelta(days=n)).isoformat()  # noqa: E731

    # 1. À réception de l'audio : échéance prévisionnelle calculée et historisée
    d = _creer(client, h, c, duree=45, reception=auj, criteres_tarif={}, qualifier=True)
    assert d["date_limite"] == j(7) and d["echeance_figee_le"] is None
    assert _historique(db, d["id"], "echeance_initiale")[0].detail["nouveau"] == j(7)

    # 2. Avant attribution : un changement de règles recalcule l'échéance (tracé)
    _modifier_regles(client, h, 10)
    assert client.get(f"/api/v1/dossiers/{d['id']}", headers=h).json()["date_limite"] == j(10)
    rec = _historique(db, d["id"], "echeance_recalculee")[-1].detail
    assert (rec["ancien"], rec["nouveau"]) == (j(7), j(10))

    # 3. Attribution : échéance figée et conservée dans l'historique
    aff = client.post(f"/api/v1/dossiers/{d['id']}/affectations", headers=h, json={"prestataire_id": str(p.id)}).json()
    fig = client.get(f"/api/v1/dossiers/{d['id']}", headers=h).json()
    assert fig["echeance_figee_le"] is not None
    gel = _historique(db, d["id"], "echeance_figee")[0]
    assert gel.detail["nouveau"] == j(10) and gel.utilisateur_id == admin.id

    # 4. Une modification ultérieure des règles ne la change plus, même après retrait de la mission
    _modifier_regles(client, h, 30)
    assert client.get(f"/api/v1/dossiers/{d['id']}", headers=h).json()["date_limite"] == j(10)
    client.post(f"/api/v1/affectations/{aff['id']}/retirer", headers=h, json={"motif": "indisponible"})
    _modifier_regles(client, h, 40)
    assert client.get(f"/api/v1/dossiers/{d['id']}", headers=h).json()["date_limite"] == j(10)
    assert client.post(f"/api/v1/dossiers/{d['id']}/echeance/recalculer", headers=h).status_code == 409
    assert client.patch(f"/api/v1/dossiers/{d['id']}", headers=h, json={"date_limite": None}).status_code == 409
    q = client.post(f"/api/v1/dossiers/{d['id']}/qualifier", headers=h,
                    json={"criteres_tarif": {}, "duree_audio_minutes": 300}).json()
    assert q["date_limite"] == j(10)


def test_modification_manuelle_tracee(client, f, mission, coord, db):
    d, h = mission["dossier_id"], mission["admin_h"]
    avant = client.get(f"/api/v1/dossiers/{d}", headers=h).json()["date_limite"]
    # dossier attribué : la modification manuelle reste possible pour les personnes autorisées
    r = client.patch(f"/api/v1/dossiers/{d}", headers=f.headers(coord), json={"date_limite": "2027-02-15"})
    assert r.status_code == 200 and r.json()["date_limite"] == "2027-02-15" and r.json()["echeance_mode"] == "manuelle"
    e = _historique(db, d, "echeance_modifiee")[-1]
    assert (e.detail["ancien"], e.detail["nouveau"]) == (avant, "2027-02-15")
    assert e.utilisateur_id == coord.id and e.timestamp is not None
    lecteur = f.headers(f.user(RoleEnum.LECTURE_SEULE))
    assert client.patch(f"/api/v1/dossiers/{d}", headers=lecteur, json={"date_limite": "2027-03-01"}).status_code == 403


def test_temps_de_relecture_sans_toucher_echeance_client(client, f, admin, parametres, db):
    h, c = f.headers(admin), f.client_()
    p, _ = f.prestataire()
    client.put("/api/v1/parametres/generaux", headers=h, json={"valeurs": {"marge_relecture_jours": 3}})
    d = _creer(client, h, c, duree=150, reception=date.today(), criteres_tarif={}, qualifier=True)  # 18 jours
    client.post(f"/api/v1/dossiers/{d['id']}/affectations", headers=h, json={"prestataire_id": str(p.id)})
    apres = client.get(f"/api/v1/dossiers/{d['id']}", headers=h).json()
    assert apres["date_limite"] == (date.today() + timedelta(days=18)).isoformat()  # échéance client intacte
    aff = db.query(Affectation).one()
    assert aff.date_limite_rendu.date() == date.today() + timedelta(days=15)  # 3 jours réservés à la relecture
