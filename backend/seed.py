"""
Script de seed — crée l'utilisateur administratrice par défaut.
Lancer après : alembic upgrade head

Usage : python seed.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app.db.session import SessionLocal
from app.models.user import User, RoleEnum
from app.core.security import hash_password

def seed():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == RoleEnum.ADMINISTRATRICE).first()
        if existing:
            print(f"Administratrice déjà existante : {existing.email}")
            return

        admin = User(
            email="admin@retranscriptions.local",
            nom="Administratrice",
            hashed_password=hash_password("ChangeMe123!"),
            role=RoleEnum.ADMINISTRATRICE,
        )
        db.add(admin)
        db.commit()
        print("✓ Administratrice créée :")
        print("  Email    : admin@retranscriptions.local")
        print("  Password : ChangeMe123!")
        print("  → Changer le mot de passe immédiatement en production !")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
