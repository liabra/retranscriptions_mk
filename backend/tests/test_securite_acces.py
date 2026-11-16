"""Failles critiques de l'audit (S1 à S5) et matrice des droits."""
import json

import pytest

from app.models.user import RoleEnum
from tests.conftest import FAKE_MP3, make_docx, docx_upload

FINANCE_GET = [
    "/api/v1/dossiers/{d}/calculs",
    "/api/v1/dossiers/{d}/facture",
    "/api/v1/dossiers/{d}/paiements-prestataires",
    "/api/v1/factures",
    "/api/v1/paiements-prestataires",
    "/api/v1/grilles",
]
INTERNE_GET = [
    "/api/v1/dossiers",
    "/api/v1/dossiers/{d}",
    "/api/v1/dossiers/{d}/livraisons",
    "/api/v1/dossiers/{d}/journal",
    "/api/v1/journal",
    "/api/v1/audios",
    "/api/v1/prestataires",
    "/api/v1/prestataires/performances",
    "/api/v1/dashboard",
    "/api/v1/dossiers/{d}/suggestions",
]


# ── S1 : aucun lien OneDrive / identifiant de stockage transmis ─────────────
def test_s1_aucune_localisation_dans_les_reponses(client, mission):
    corps = json.dumps([
        client.get("/api/v1/espace-prestataire/missions", headers=mission["presta_h"]).json(),
        client.get(f"/api/v1/dossiers/{mission['dossier_id']}", headers=mission["admin_h"]).json(),
        client.get("/api/v1/audios?statut=associe", headers=mission["admin_h"]).json(),
    ])
    for interdit in ("url_onedrive", "lien_prive", "drive_id", "item_id", "chemin_local", "stockage_ref",
                     "downloadUrl", "sharepoint", "1drv"):
        assert interdit not in corps


def test_s1_lien_prive_jamais_renvoye(client, f, admin):
    url = "https://contoso-my.sharepoint.com/:u:/g/personal/x/EabcDEF?e=secret"
    r = client.post("/api/v1/audios/lien", headers=f.headers(admin), json={"url": url})
    assert r.status_code == 201
    assert "secret" not in r.text and "sharepoint" not in r.text
    assert r.json()["disponible"] is False  # OneDrive non configuré : pas de vérification simulée
    liste = client.get("/api/v1/audios", headers=f.headers(admin)).text
    assert "sharepoint" not in liste


@pytest.mark.parametrize("url", [
    "http://contoso.sharepoint.com/x",            # pas https
    "https://evil.example.com/sharepoint.com",     # domaine non Microsoft
    "https://169.254.169.254/latest/meta-data",    # SSRF
    "https://sharepoint.com.evil.fr/a",
])
def test_s1_s3_lien_non_microsoft_refuse(client, f, admin, url):
    assert client.post("/api/v1/audios/lien", headers=f.headers(admin), json={"url": url}).status_code == 400


# ── S2 : téléchargement audio limité à l'affectation active ─────────────────
def test_s2_prestataire_affecte_telecharge_via_proxy(client, mission):
    r = client.get(f"/api/v1/espace-prestataire/missions/{mission['affectation_id']}/audio",
                   headers=mission["presta_h"])
    assert r.status_code == 200
    assert r.content == FAKE_MP3
    assert "attachment" in r.headers["content-disposition"]
    assert "location" not in r.headers


def test_s2_autre_prestataire_refuse(client, f, mission):
    _, autre = f.prestataire("Autre")
    h = f.headers(autre)
    assert client.get(f"/api/v1/espace-prestataire/missions/{mission['affectation_id']}/audio",
                      headers=h).status_code == 404
    assert client.get(f"/api/v1/espace-prestataire/missions/{mission['affectation_id']}",
                      headers=h).status_code == 404
    assert client.get("/api/v1/espace-prestataire/missions", headers=h).json() == []
    # accès « interne » direct à l'audio interdit
    assert client.get(f"/api/v1/audios/{mission['audio_id']}/fichier", headers=h).status_code == 403


def test_s2_acces_retire_apres_retrait(client, mission):
    r = client.post(f"/api/v1/affectations/{mission['affectation_id']}/retirer", headers=mission["admin_h"],
                    json={"motif": "Indisponibilité"})
    assert r.status_code == 200
    assert client.get(f"/api/v1/espace-prestataire/missions/{mission['affectation_id']}/audio",
                      headers=mission["presta_h"]).status_code == 404


def test_s2_compte_prestataire_sans_fiche_refuse(client, f):
    u = f.user(RoleEnum.RETRANSCRIPTEUR)  # pas de prestataire_id : plus de liaison par email
    assert client.get("/api/v1/espace-prestataire/missions", headers=f.headers(u)).status_code == 403


# ── S3 : plus aucune route d'attachement d'URL arbitraire ───────────────────
def test_s3_routes_historiques_supprimees(client, mission):
    d = mission["dossier_id"]
    for h in (mission["presta_h"], mission["admin_h"]):
        assert client.post(f"/api/v1/dossiers/{d}/fichiers", headers=h,
                           json={"type_document": "audio_brut", "nom_fichier": "x", "url_onedrive": "https://x"}
                           ).status_code in (404, 405)
        assert client.post(f"/api/v1/dossiers/{d}/upload", headers=h).status_code in (404, 405)


def test_s3_prestataire_ne_peut_pas_ajouter_audio(client, mission):
    r = client.post("/api/v1/audios/lien", headers=mission["presta_h"],
                    json={"url": "https://contoso.sharepoint.com/x"})
    assert r.status_code == 403


# ── S4 : données financières réservées ──────────────────────────────────────
@pytest.mark.parametrize("role", [RoleEnum.RETRANSCRIPTEUR, RoleEnum.CLIENT, RoleEnum.LECTURE_SEULE,
                                  RoleEnum.COORDINATRICE])
def test_s4_finance_interdite(client, f, mission, role):
    if role == RoleEnum.RETRANSCRIPTEUR:
        h = mission["presta_h"]
    elif role == RoleEnum.CLIENT:
        h = f.headers(f.user(role, client_id=mission["client"].id))
    else:
        h = f.headers(f.user(role))
    for path in FINANCE_GET:
        r = client.get(path.format(d=mission["dossier_id"]), headers=h)
        assert r.status_code == 403, (role, path, r.status_code)


def test_s4_comptabilite_et_admin_autorises(client, f, mission):
    h = f.headers(f.user(RoleEnum.COMPTABILITE))
    assert client.get("/api/v1/factures", headers=h).status_code == 200
    assert client.get(f"/api/v1/dossiers/{mission['dossier_id']}/calculs", headers=mission["admin_h"]).status_code == 200


def test_s4_permission_finance_deleguee_a_la_coordinatrice(client, f, admin, coord):
    hc = f.headers(coord)
    assert client.get("/api/v1/factures", headers=hc).status_code == 403
    r = client.patch(f"/api/v1/auth/users/{coord.id}", headers=f.headers(admin),
                     json={"permissions": {"finance.voir": True, "utilisateurs.gerer": True, "inconnue": True}})
    assert r.status_code == 200
    assert "utilisateurs.gerer" not in r.json()["user"]["permissions"]  # jamais délégable
    assert client.get("/api/v1/factures", headers=hc).status_code == 200
    assert client.get("/api/v1/auth/users", headers=hc).status_code == 403


def test_s4_espace_prestataire_sans_montant(client, mission):
    corps = client.get("/api/v1/espace-prestataire/missions", headers=mission["presta_h"]).text
    for interdit in ("montant", "marge", "tarif", "facture", "iban", "notes_internes", "score", "client_id"):
        assert interdit not in corps


# ── S5 : un client ne voit que ses dossiers ─────────────────────────────────
def test_s5_client_cloisonne(client, f, mission):
    autre_client = f.client_("Autre CSE")
    u = f.user(RoleEnum.CLIENT, client_id=autre_client.id)
    h = f.headers(u)
    assert client.get(f"/api/v1/dossiers/{mission['dossier_id']}", headers=h).status_code == 403
    assert client.get("/api/v1/espace-client/dossiers", headers=h).json() == []
    proprio = f.user(RoleEnum.CLIENT, client_id=mission["client"].id)
    dossiers = client.get("/api/v1/espace-client/dossiers", headers=f.headers(proprio)).json()
    assert len(dossiers) == 1 and "notes_internes" not in dossiers[0]


# ── Matrice : rôles externes exclus de toutes les routes internes ──────────
@pytest.mark.parametrize("path", INTERNE_GET)
def test_routes_internes_interdites_aux_externes(client, f, mission, path):
    client_user = f.user(RoleEnum.CLIENT, client_id=mission["client"].id)
    for h in (mission["presta_h"], f.headers(client_user)):
        r = client.get(path.format(d=mission["dossier_id"]), headers=h)
        assert r.status_code == 403, (path, r.status_code)


def test_lecture_seule_ne_modifie_rien(client, f, mission):
    h = f.headers(f.user(RoleEnum.LECTURE_SEULE))
    assert client.get(f"/api/v1/dossiers/{mission['dossier_id']}", headers=h).status_code == 200
    assert client.patch(f"/api/v1/dossiers/{mission['dossier_id']}", headers=h, json={"titre": "x"}).status_code == 403
    assert client.post(f"/api/v1/dossiers/{mission['dossier_id']}/livraisons", headers=h,
                       files=docx_upload(make_docx())).status_code == 403


def test_iban_reserve_administratrice(client, f, admin, coord):
    p, _ = f.prestataire()
    r = client.patch(f"/api/v1/prestataires/{p.id}", headers=f.headers(admin), json={"iban": "FR7630006000011234567890189"})
    assert r.status_code == 200 and "FR76" not in r.text and r.json()["iban_renseigne"] is True
    assert client.get(f"/api/v1/prestataires/{p.id}/iban", headers=f.headers(coord)).status_code == 403
    assert client.get(f"/api/v1/prestataires/{p.id}/iban", headers=f.headers(admin)).json()["iban"].startswith("FR76")


def test_en_tetes_securite(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert client.get("/docs").status_code == 404
