"""Calcul tarifaire, facturation (bug payeur), encaissements, paiements prestataires."""
from decimal import Decimal

import pytest

from app.models.paiement import PaiementPrestataire
from app.models.pricing.calcul import CalculTarifaire
from app.models.pricing.grille import GrilleTarifaire, TypeGrilleEnum
from app.models.user import RoleEnum
from tests.conftest import make_docx, docx_upload


@pytest.fixture
def grilles():
    from seed_grilles import seed_grilles
    seed_grilles()


@pytest.fixture
def valide(client, f, mission, grilles):
    """Mission validée à 15 pages, prête à facturer."""
    aid, d, ah = mission["affectation_id"], mission["dossier_id"], mission["admin_h"]
    client.post(f"/api/v1/espace-prestataire/missions/{aid}/livraisons", headers=mission["presta_h"],
                files=docx_upload(make_docx()))
    client.post(f"/api/v1/dossiers/{d}/relecture/commencer", headers=ah)
    client.post(f"/api/v1/dossiers/{d}/relecture/terminer", headers=ah)
    lid = client.get(f"/api/v1/dossiers/{d}", headers=ah).json()["livraisons"][0]["id"]
    r = client.post(f"/api/v1/dossiers/{d}/valider", headers=ah, json={"livraison_id": lid, "nombre_pages_final": "15"})
    assert r.status_code == 200
    return mission


def _facturer(client, m):
    d, h = m["dossier_id"], m["admin_h"]
    calc = client.post(f"/api/v1/dossiers/{d}/calculer", headers=h, json={}).json()
    assert client.post(f"/api/v1/calculs/{calc['id']}/valider", headers=h).status_code == 200
    return client.post(f"/api/v1/dossiers/{d}/generer-facture", headers=h, json={"tva_applicable": False})


def test_calcul_grille_reelle_sans_auto_validation(client, valide, db):
    r = client.post(f"/api/v1/dossiers/{valide['dossier_id']}/calculer", headers=valide["admin_h"], json={})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["statut"] == "estimatif"  # B5 : plus d'auto-validation
    assert Decimal(c["montant_client_final"]) == Decimal("100.00")  # grille client : 10–20 pages → 100 €
    assert Decimal(c["montant_correcteur"]) == Decimal("0.00")  # pas de correcteur externe
    assert c["regles_appliquees"]


def test_calcul_refuse_sans_grille_client(client, valide, db):
    for g in db.query(GrilleTarifaire).filter(GrilleTarifaire.type == TypeGrilleEnum.CLIENT).all():
        g.active = False
    db.commit()
    r = client.post(f"/api/v1/dossiers/{valide['dossier_id']}/calculer", headers=valide["admin_h"], json={})
    assert r.status_code == 400 and "grille" in r.json()["detail"].lower()
    assert db.query(CalculTarifaire).count() == 0  # aucun forfait inventé


def test_facture_exige_calcul_valide(client, valide):
    d, h = valide["dossier_id"], valide["admin_h"]
    client.post(f"/api/v1/dossiers/{d}/calculer", headers=h, json={})
    assert client.post(f"/api/v1/dossiers/{d}/generer-facture", headers=h, json={}).status_code == 409


def test_generation_facture_bug_payeur_corrige(client, valide, db):
    r = _facturer(client, valide)
    assert r.status_code == 201, r.text  # B1 : plus d'erreur 500 après création
    fac = r.json()
    assert fac["numero_facture"].startswith("FAC-") and fac["payeur_nom"] == "CSE Exemple"
    assert Decimal(fac["montant_ttc"]) == Decimal("100.00")
    p = db.query(PaiementPrestataire).one()
    assert p.prestataire_id == valide["presta"].id and p.statut.value == "a_payer"
    d = client.get(f"/api/v1/dossiers/{valide['dossier_id']}", headers=valide["admin_h"]).json()
    assert d["statut_facturation"] == "emise" and d["statut_production"] == "valide"
    # double facturation refusée
    assert client.post(f"/api/v1/dossiers/{valide['dossier_id']}/generer-facture", headers=valide["admin_h"],
                       json={}).status_code == 409


def test_recalcul_interdit_apres_facture(client, valide):
    _facturer(client, valide)
    r = client.post(f"/api/v1/dossiers/{valide['dossier_id']}/calculer", headers=valide["admin_h"], json={})
    assert r.status_code == 409


def test_encaissements(client, valide):
    fac = _facturer(client, valide).json()
    h = valide["admin_h"]
    url = f"/api/v1/factures/{fac['id']}/encaissements"
    assert client.post(url, headers=h, json={"montant": "150", "date_encaissement": "2026-11-10"}).status_code == 400
    r = client.post(url, headers=h, json={"montant": "40", "date_encaissement": "2026-11-10", "mode": "virement"})
    assert r.json()["statut_paiement"] == "partiellement"
    r = client.post(url, headers=h, json={"montant": "60", "date_encaissement": "2026-11-12"})
    assert r.json()["statut_paiement"] == "soldee" and Decimal(r.json()["reste_a_encaisser"]) == 0
    d = client.get(f"/api/v1/dossiers/{valide['dossier_id']}", headers=h).json()
    assert d["statut_facturation"] == "reglee"
    # facture réglée : annulation impossible
    assert client.post(f"/api/v1/factures/{fac['id']}/annuler", headers=h, json={"motif": "erreur"}).status_code == 409


def test_annulation_conserve_numero(client, valide):
    h = valide["admin_h"]
    fac = _facturer(client, valide).json()
    assert client.delete(f"/api/v1/factures/{fac['id']}", headers=h).status_code == 405  # plus de suppression
    r = client.post(f"/api/v1/factures/{fac['id']}/annuler", headers=h, json={"motif": "Erreur de payeur"})
    assert r.status_code == 200 and r.json()["annulee_le"]
    r2 = client.post(f"/api/v1/dossiers/{valide['dossier_id']}/generer-facture", headers=h, json={})
    assert r2.status_code == 201
    assert r2.json()["numero_facture"] != fac["numero_facture"]
    assert client.get("/api/v1/factures?vue=annulees", headers=h).json()["items"][0]["numero_facture"] == fac["numero_facture"]


def test_paiement_prestataire_machine_etats(client, valide):
    _facturer(client, valide)
    h = valide["admin_h"]
    p = client.get("/api/v1/paiements-prestataires", headers=h).json()[0]
    url = f"/api/v1/paiements-prestataires/{p['id']}"
    assert client.patch(url, headers=h, json={"statut": "paye"}).status_code == 409  # étape « validé » obligatoire
    assert client.patch(url, headers=h, json={"ajustement_manuel": "5"}).status_code == 400  # motif requis
    assert client.patch(url, headers=h, json={"ajustement_manuel": "5", "motif_ajustement": "Urgence"}).status_code == 200
    assert client.patch(url, headers=h, json={"statut": "valide"}).status_code == 200
    assert client.patch(url, headers=h, json={"statut": "paye"}).status_code == 400  # date de virement requise
    r = client.patch(url, headers=h, json={"statut": "paye", "date_virement": "2026-11-15"})
    assert r.status_code == 200
    assert client.patch(url, headers=h, json={"ajustement_manuel": "0", "motif_ajustement": "x"}).status_code == 409


def test_facture_html_echappee(client, valide, db):
    valide["client"].nom = "<script>alert(1)</script>"
    db.merge(valide["client"])
    db.commit()
    fac = _facturer(client, valide).json()
    r = client.get(f"/api/v1/factures/{fac['id']}/html", headers=valide["admin_h"])
    assert "<script>alert(1)</script>" not in r.text and "&lt;script&gt;" in r.text


def test_grille_utilisee_figee(client, valide, f, admin, db):
    _facturer(client, valide)
    calc = db.query(CalculTarifaire).first()
    gid = next(iter(calc.grilles_version_snap))
    h = f.headers(admin)
    regle = client.get(f"/api/v1/grilles/{gid}/regles", headers=h).json()[0]
    assert client.patch(f"/api/v1/regles/{regle['id']}", headers=h, json={"valeur": "999"}).status_code == 409
    r = client.post(f"/api/v1/grilles/{gid}/nouvelle-version", headers=h)
    assert r.status_code == 201 and r.json()["active"] is False


def test_comptabilite_ne_valide_pas_les_pv(client, f, valide):
    h = f.headers(f.user(RoleEnum.COMPTABILITE))
    assert client.post(f"/api/v1/dossiers/{valide['dossier_id']}/relecture/commencer", headers=h).status_code == 403
    assert client.get("/api/v1/factures?vue=a_etablir", headers=h).json()["items"][0]["reference"]


def _ancien_forfait(p: Decimal) -> Decimal:
    """Copie de l'ancien `_forfait_a2c` supprimé : référence de non-régression."""
    paliers = [(9, 50), (20, 100), (30, 150), (40, 200), (50, 250), (60, 300), (70, 350), (80, 400), (90, 450), (100, 500)]
    for maxi, montant in paliers:
        if p <= maxi:
            return Decimal(montant).quantize(Decimal("0.01"))
    return (p * Decimal("5.00")).quantize(Decimal("0.01"))


@pytest.mark.parametrize("pages", [1, 9, 10, 15, 20, 21, 30, 31, 45, 55, 69, 70, 80, 81, 90, 91, 100, 101, 137])
def test_grille_client_identique_ancien_bareme(db, f, grilles, pages):
    from datetime import datetime, timezone
    from app.models.dossier import Dossier, TypeInstanceEnum
    from app.services.calcul_service import run_calcul
    c = f.client_()
    d = Dossier(reference=f"T-{pages}", type_instance=TypeInstanceEnum.CE, client_id=c.id,
                date_reception_audio=datetime.now(timezone.utc), criteres_tarif={})
    db.add(d)
    db.flush()
    calcul = run_calcul(d, Decimal(pages), None, db)
    assert calcul.montant_client_final == _ancien_forfait(Decimal(pages))
    db.rollback()
