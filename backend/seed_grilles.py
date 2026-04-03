"""
Seed des grilles tarifaires minimales pour les tests métier.
Idempotent — vérifie si les grilles existent avant de les créer.

Usage :
    python seed_grilles.py

Tarifs de démonstration (à ajuster selon le réel) :
  Client      : 0.45 €/page (base) + majoration urgence 30%
  Retrans.    : 0.25 €/page (base) + majoration urgence 20%
  Correcteur  : 0.12 €/page (base)
"""
import os
from datetime import date
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

import app.db.base  # noqa
from app.db.session import SessionLocal
from app.models.pricing.grille import GrilleTarifaire, TypeGrilleEnum, CibleGrilleEnum
from app.models.pricing.regle import RegleTarifaire, TypeRegleEnum, ConditionTypeEnum, ModeCalculEnum


GRILLES_DEMO = [
    {
        "nom": "Tarif client standard",
        "type": TypeGrilleEnum.CLIENT,
        "cible": CibleGrilleEnum.GLOBAL,
        "version": "1.0",
        "regles": [
            {
                "libelle": "Tarif de base client",
                "type_regle": TypeRegleEnum.BASE,
                "condition_type": ConditionTypeEnum.TOUJOURS,
                "mode_calcul": ModeCalculEnum.PAR_PAGE,
                "valeur": Decimal("0.45"),
                "unite": "€/page",
                "priorite": 10,
            },
        ],
    },
    {
        "nom": "Tarif retranscripteur standard",
        "type": TypeGrilleEnum.RETRANSCRIPTEUR,
        "cible": CibleGrilleEnum.GLOBAL,
        "version": "1.0",
        "regles": [
            {
                "libelle": "Tarif de base retranscripteur",
                "type_regle": TypeRegleEnum.BASE,
                "condition_type": ConditionTypeEnum.TOUJOURS,
                "mode_calcul": ModeCalculEnum.PAR_PAGE,
                "valeur": Decimal("0.25"),
                "unite": "€/page",
                "priorite": 10,
            },
        ],
    },
    {
        "nom": "Tarif correcteur standard",
        "type": TypeGrilleEnum.CORRECTEUR,
        "cible": CibleGrilleEnum.GLOBAL,
        "version": "1.0",
        "regles": [
            {
                "libelle": "Tarif de base correcteur",
                "type_regle": TypeRegleEnum.BASE,
                "condition_type": ConditionTypeEnum.TOUJOURS,
                "mode_calcul": ModeCalculEnum.PAR_PAGE,
                "valeur": Decimal("0.12"),
                "unite": "€/page",
                "priorite": 10,
            },
        ],
    },
    {
        "nom": "Majoration urgence",
        "type": TypeGrilleEnum.URGENCE,
        "cible": CibleGrilleEnum.GLOBAL,
        "version": "1.0",
        "regles": [
            {
                "libelle": "Majoration urgence client +30%",
                "type_regle": TypeRegleEnum.MAJORATION,
                "condition_type": ConditionTypeEnum.SI_URGENCE,
                "mode_calcul": ModeCalculEnum.POURCENTAGE_BASE,
                "valeur": Decimal("30.00"),
                "unite": "%",
                "priorite": 50,
            },
        ],
    },
]


def seed_grilles():
    db = SessionLocal()
    try:
        created = 0
        for spec in GRILLES_DEMO:
            existing = db.query(GrilleTarifaire).filter(
                GrilleTarifaire.nom == spec["nom"],
                GrilleTarifaire.type == spec["type"],
            ).first()

            if existing:
                print(f"  → Grille déjà existante : {spec['nom']}")
                continue

            grille = GrilleTarifaire(
                nom=spec["nom"],
                type=spec["type"],
                cible=spec["cible"],
                version=spec["version"],
                date_debut=date.today(),
                active=True,
            )
            db.add(grille)
            db.flush()

            for r in spec["regles"]:
                regle = RegleTarifaire(
                    grille_id=grille.id,
                    libelle=r["libelle"],
                    type_regle=r["type_regle"],
                    condition_type=r["condition_type"],
                    mode_calcul=r["mode_calcul"],
                    valeur=r["valeur"],
                    unite=r.get("unite"),
                    priorite=r.get("priorite", 100),
                    cumulable=True,
                    actif=True,
                )
                db.add(regle)

            db.commit()
            print(f"  ✓ Grille créée : {spec['nom']}")
            created += 1

        print(f"\nSeed grilles terminé. {created} grille(s) créée(s).")
    finally:
        db.close()


if __name__ == "__main__":
    seed_grilles()
