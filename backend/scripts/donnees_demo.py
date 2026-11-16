"""
Jeu de données de DÉMONSTRATION (développement uniquement).

Crée des clients, des retranscripteurs (avec accès) et des dossiers à toutes les étapes,
en passant par l'API réelle (mêmes contrôles que l'interface). Refuse de s'exécuter en production.

Usage : APP_ENV=development python scripts/donnees_demo.py
Les comptes de démonstration utilisent le mot de passe affiché en fin d'exécution.
"""
import io
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.core.config import settings  # noqa: E402

if settings.is_production:
    sys.exit("Refusé : jeu de démonstration interdit en production.")

import docx  # noqa: E402
from docx.shared import Pt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.db.base  # noqa: E402,F401
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, RoleEnum  # noqa: E402

MDP_DEMO = "Demo-A2C-2026!"
MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 4096


def pv(font="Comic Sans MS", size=12, n=8) -> bytes:
    d = docx.Document()
    d.styles["Normal"].font.name = font
    d.styles["Normal"].font.size = Pt(size)
    d.add_paragraph("PROCÈS-VERBAL DE LA RÉUNION ORDINAIRE")
    for i in range(n):
        d.add_paragraph(f"Point {i + 1} — Le secrétaire présente le point et les élus échangent sur les orientations.")
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def main() -> None:
    db = SessionLocal()
    admin = db.query(User).filter(User.role == RoleEnum.ADMINISTRATRICE, User.actif == True).first()  # noqa: E712
    if not admin:
        sys.exit("Lancez d'abord seed.py")
    demo_admin = db.query(User).filter(User.email == "demo.admin@a2c.example").first()
    if not demo_admin:
        demo_admin = User(email="demo.admin@a2c.example", nom="Sophie Admin (démo)", role=RoleEnum.ADMINISTRATRICE,
                          hashed_password=hash_password(MDP_DEMO))
        db.add(demo_admin)
        db.add(User(email="demo.coord@a2c.example", nom="Nadia Coordinatrice (démo)", role=RoleEnum.COORDINATRICE,
                    hashed_password=hash_password(MDP_DEMO)))
        db.commit()
    c = TestClient(app)
    h = {"Authorization": f"Bearer {create_access_token(demo_admin.id, demo_admin.token_version)}"}

    def post(url, **kw):
        r = c.post(f"/api/v1{url}", headers=h, **kw)
        assert r.status_code < 300, (url, r.status_code, r.text)
        return r.json()

    clients = [post("/clients", json={"nom": n, "type": t, "entreprise_mere": e, "contact_principal": p,
                                      "conditions_paiement": "30 jours"})
               for n, t, e, p in (("CSE Ateliers du Rhône", "CE", "Ateliers du Rhône SA", "Marc Bernard"),
                                  ("CMAS Énergie Sud", "CMAS", "Énergie Sud", "Claire Petit"),
                                  ("CSSCT Logistique Nord", "CSSCT", "Logistique Nord", "Paul Roux"))]
    prestas = []
    for nom, spec in (("Léa Durand", ["CE", "CSSCT"]), ("Karim Benali", ["CMAS"]), ("Inès Moreau", [])):
        p = post("/prestataires", json={"nom": nom, "email": f"{nom.split()[0].lower().replace('é', 'e').replace('è', 'e')}.demo@a2c.example", "specialites": spec})
        u = User(email=p["email"], nom=nom, role=RoleEnum.RETRANSCRIPTEUR, prestataire_id=p["id"],
                 hashed_password=hash_password(MDP_DEMO))
        db.add(u)
        db.commit()
        prestas.append((p, {"Authorization": f"Bearer {create_access_token(u.id, 0)}"}))

    def dossier(i, client, titre, etape, presta=0, font="Comic Sans MS", jours=10):
        audio = post("/audios/fichier", files={"file": (f"seance_{i}.mp3", MP3, "audio/mpeg")},
                     data={"client_id": client["id"], "duree_minutes": str(45 + 30 * i)})
        if etape == "audio":
            return
        d = post("/dossiers", json={
            "type_instance": client["type"], "client_id": client["id"], "titre": titre, "audio_id": audio["id"],
            "date_seance": (datetime.now() - timedelta(days=12)).date().isoformat(),
            "date_limite": (datetime.now() + timedelta(days=jours)).date().isoformat(),
            "criteres_tarif": {"urgence": i % 4 == 0}, "qualifier": etape != "a_qualifier",
        })
        if etape in ("a_qualifier", "a_attribuer"):
            return
        p, ph = prestas[presta]
        aff = post(f"/dossiers/{d['id']}/affectations", json={
            "prestataire_id": p["id"], "commentaire": "Merci de respecter le modèle A2C.",
            "date_limite_rendu": (datetime.now(timezone.utc) + timedelta(days=jours if etape != "retard" else -2)).isoformat()})
        if etape in ("attribue", "retard"):
            return
        c.post(f"/api/v1/espace-prestataire/missions/{aff['id']}/commencer", headers=ph)
        if etape == "en_cours":
            return
        r = c.post(f"/api/v1/espace-prestataire/missions/{aff['id']}/livraisons", headers=ph,
                   files={"file": ("PV.docx", pv(font=font), "application/octet-stream")})
        assert r.status_code == 201, r.text
        if etape == "livre":
            return
        post(f"/dossiers/{d['id']}/relecture/commencer")
        if etape == "a_relire":
            return
        if etape == "correction":
            post(f"/dossiers/{d['id']}/corrections", json={"message": "Merci d'appliquer Comic Sans MS 12 sur tout le document."})
            return
        post(f"/dossiers/{d['id']}/relecture/terminer")
        if etape == "a_controler":
            return
        lid = c.get(f"/api/v1/dossiers/{d['id']}", headers=h).json()["livraisons"][0]["id"]
        post(f"/dossiers/{d['id']}/valider", json={"livraison_id": lid, "nombre_pages_final": str(12 + i * 3)})
        if etape == "valide":
            return
        calc = post(f"/dossiers/{d['id']}/calculer", json={})
        post(f"/calculs/{calc['id']}/valider")
        fac = post(f"/dossiers/{d['id']}/generer-facture", json={"date_echeance": (datetime.now() + timedelta(days=30)).date().isoformat()})
        if etape == "regle":
            post(f"/factures/{fac['id']}/encaissements", json={"montant": fac["montant_ttc"], "date_encaissement": datetime.now().date().isoformat(), "mode": "virement"})

    plan = [
        ("audio", None), ("a_qualifier", "Réunion extraordinaire"), ("a_attribuer", "Plénière de novembre"),
        ("attribue", "Commission santé"), ("retard", "Réunion ordinaire d'octobre"), ("en_cours", "Bilan social"),
        ("livre", "Consultation orientations stratégiques"), ("a_relire", "Plénière de septembre"),
        ("correction", "Réunion budget ASC"), ("a_controler", "Commission formation"), ("valide", "Plénière de juillet"),
        ("facture", "Plénière de juin"), ("regle", "Plénière de mai"),
    ]
    for i, (etape, titre) in enumerate(plan):
        dossier(i, clients[i % 3], titre, etape, presta=i % 3, font="Arial" if etape == "correction" else "Comic Sans MS")
    db.close()
    print("✓ Données de démonstration créées.")
    print(f"  Comptes de démonstration (mot de passe : {MDP_DEMO}) :")
    print("  demo.admin@a2c.example · demo.coord@a2c.example · lea.demo@a2c.example · karim.demo@a2c.example · ines.demo@a2c.example")


if __name__ == "__main__":
    main()
