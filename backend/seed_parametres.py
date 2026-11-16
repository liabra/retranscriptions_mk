"""
Configuration initiale des délais et paramètres métier — exécutée UNE seule fois
(marqueur en base) : la cliente peut ensuite tout modifier ou supprimer sans que
l'amorçage ne réécrive ses choix.

Valeurs reprises de l'ancien code (aucune valeur nouvelle) :
- délai de livraison « modalités A2C » : audio ≤ 1 h → 7 j ; ≤ 4 h → 18 j ; au-delà → 25 j
  (désormais compté depuis la réception de l'audio) — à confirmer par la cliente ;
- dossier signalé urgent si l'échéance client est à moins de 2 jours ;
- alerte « échéance proche » 48 h avant l'échéance du retranscripteur ;
- rendu attendu du retranscripteur : à l'échéance client (marge de relecture 0 jour).
"""
from dotenv import load_dotenv

load_dotenv()

import app.db.base  # noqa
from app.db.session import SessionLocal
from app.models.refonte import RegleDelai, Parametre

MARQUEUR = "_initialisation_delais"
DESCRIPTION = "Reprise de la règle existante (modalités A2C) — à confirmer par la cliente"
REGLES = [
    ("Audio jusqu'à 1 h", 10, None, 60, 7),
    ("Audio de plus de 1 h à 4 h", 20, 60, 240, 18),
    ("Audio de plus de 4 h", 30, 240, None, 25),
]
PARAMETRES = {"seuil_urgence_jours": 2, "alerte_echeance_heures": 48, "marge_relecture_jours": 0}


def seed_parametres() -> None:
    db = SessionLocal()
    try:
        if db.query(Parametre).filter(Parametre.cle == MARQUEUR).first():
            return
        if not db.query(RegleDelai).count():
            for lib, prio, mini, maxi, jours in REGLES:
                db.add(RegleDelai(libelle=lib, priorite=prio, duree_min_minutes=mini, duree_max_minutes=maxi,
                                  delai_jours=jours, type_jours="calendaires", description=DESCRIPTION))
        for cle, val in PARAMETRES.items():
            if not db.query(Parametre).filter(Parametre.cle == cle).first():
                db.add(Parametre(cle=cle, valeur={"valeur": val}))
        db.add(Parametre(cle=MARQUEUR, valeur={"valeur": True}))
        db.commit()
        print("✓ Délais et paramètres initiaux créés")
    finally:
        db.close()


if __name__ == "__main__":
    seed_parametres()
