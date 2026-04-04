"""
Seed des grilles tarifaires A2C.
Idempotent — vérifie si les grilles existent avant de les créer.

Usage :
    python seed_grilles.py

Tarifs réels A2C (modalités de retranscription) :
  Grille client : forfait par tranche de pages
    1–9 p   → 50 €    |  10–20 p  → 100 €  |  21–30 p  → 150 €
    31–40 p → 200 €   |  41–50 p  → 250 €  |  51–60 p  → 300 €
    61–70 p → 350 €   |  71–80 p  → 400 €  |  81–90 p  → 450 €
    91–100 p→ 500 €

  NOTE : le moteur PAR_PAGE utilise un taux moyen (5 €/page).
  Le forfait réel est calculé et affiché directement dans l'interface
  (composant TarifForfait) à partir du nombre de pages final.

  Retranscripteur : 0.25 €/page (base)
  Correcteur      : 0.12 €/page (base)
  Urgence         : +30 % sur base client
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
        "version": "2.0",
        "regles": [
            {
                # Taux moyen approché : 500 € / 100 pages = 5 €/page.
                # Le forfait réel par tranche est calculé dans le frontend (TarifForfait).
                "libelle": "Taux moyen client (référence moteur)",
                "type_regle": TypeRegleEnum.BASE,
                "condition_type": ConditionTypeEnum.TOUJOURS,
                "mode_calcul": ModeCalculEnum.PAR_PAGE,
                "valeur": Decimal("5.00"),
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
