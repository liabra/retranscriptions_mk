"""
Amorçage des comptes internes.

- Si aucune administratrice active n'existe, crée les deux comptes internes initiaux.
  Seules les empreintes bcrypt figurent ici ; les mots de passe ont été remis une seule fois
  à l'administratrice et un changement est IMPOSÉ à la première connexion.
- Désactive l'ancien compte par défaut (admin@retranscriptions.local / mot de passe public)
  dès qu'une autre administratrice active existe.
- N'affiche jamais de mot de passe.

Usage : python seed.py
"""
from dotenv import load_dotenv

load_dotenv()

import app.db.base  # noqa — charge tous les modèles
from app.core.security import verify_password
from app.db.session import SessionLocal
from app.models.user import User, RoleEnum

COMPTES_INITIAUX = [
    {
        "email": "administratrice@a2c.example",
        "nom": "Administratrice A2C",
        "role": RoleEnum.ADMINISTRATRICE,
        "hash": "$2b$12$S/uZNW7NNGOy6CJS4i/6OuiAKpIP2Run2G0cA2XaS06OWzC6jL3/K",
    },
    {
        "email": "coordinatrice@a2c.example",
        "nom": "Coordinatrice A2C",
        "role": RoleEnum.COORDINATRICE,
        "hash": "$2b$12$83612MoCjWR2P/WvdctMpOc4ryrgHlHZ2H3eqydo5p8m0lcdWl5qa",
    },
]

ANCIEN_COMPTE_DEFAUT = "admin@retranscriptions.local"
ANCIEN_MOT_DE_PASSE_PUBLIC = "ChangeMe123!"  # fix S13 : mot de passe déjà publié dans les logs, jamais réutilisé


def seed() -> None:
    db = SessionLocal()
    try:
        admin_actif = db.query(User).filter(
            User.role == RoleEnum.ADMINISTRATRICE, User.actif == True,  # noqa: E712
            User.email != ANCIEN_COMPTE_DEFAUT,
        ).first()
        if not admin_actif:
            for c in COMPTES_INITIAUX:
                if db.query(User).filter(User.email == c["email"]).first():
                    continue
                db.add(User(email=c["email"], nom=c["nom"], role=c["role"], hashed_password=c["hash"],
                            must_change_password=True))
                print(f"✓ Compte initial créé : {c['email']} (changement de mot de passe imposé)")
            db.flush()

        ancien = db.query(User).filter(User.email == ANCIEN_COMPTE_DEFAUT, User.actif == True).first()  # noqa: E712
        if ancien and verify_password(ANCIEN_MOT_DE_PASSE_PUBLIC, ancien.hashed_password):
            ancien.actif = False
            ancien.token_version = (ancien.token_version or 0) + 1
            print(f"✓ Ancien compte par défaut désactivé : {ANCIEN_COMPTE_DEFAUT}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
