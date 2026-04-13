"""
Seed des grilles tarifaires A2C.
Idempotent — vérifie si les grilles existent avant de les créer.
Désactive les anciennes grilles placeholder (taux 0.25€/page) quand les nouvelles sont créées.

Usage :
    python seed_grilles.py

──────────────────────────────────────────────────────────────────────────────
TARIFS RÉELS A2C (modalités de retranscription signées)
──────────────────────────────────────────────────────────────────────────────

GRILLE CLIENT (inchangée — utilisée pour la facturation) :
  1–9 p   → 50 €   |  10–20 p → 100 €  |  21–30 p → 150 €  | 31–40 p → 200 €
  41–50 p → 250 €  |  51–60 p → 300 €  |  61–70 p → 350 €  | 71–80 p → 400 €
  81–90 p → 450 €  |  91–100 p→ 500 €

GRILLE RETRANSCRIPTEUR FRANCE (convention collaboration France) :
  Identique aux tarifs client (marge = 0 côté retranscription France).

GRILLE RETRANSCRIPTEUR TOGO (convention collaboration Togo) :
  1–9 p   → 25 €   |  10–20 p →  50 €  |  21–30 p →  75 €  | 31–40 p → 100 €
  41–50 p → 125 €  |  51–60 p → 150 €  |  61–80 p → 250 €  | 81–100 p→ 350 €

GRILLE CORRECTEUR : les documents ne précisent pas de tarif correcteur séparé.
  Les grilles correcteur existantes sont conservées et peuvent être ajustées
  manuellement via l'interface Grilles tarifaires.

Majoration urgence : +30 % sur base client (inchangée).

──────────────────────────────────────────────────────────────────────────────
LOGIQUE DES RÈGLES PAR TRANCHE
──────────────────────────────────────────────────────────────────────────────
Le moteur applique les règles BASE dans l'ordre de priorité croissant.
La première règle BASE dont la condition SI_VOLUME est satisfaite est retenue ;
les règles BASE suivantes sont ignorées.
→ Les tranches les plus hautes ont la priorité la plus basse (s'appliquent en premier).
  Ex : 85 pages → prio 10 (>=91) non satisfait, prio 20 (>=81) satisfait → 450 €.
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


# ── Règles par tranche pour les retranscripteurs ──────────────────────────────

def _regles_retranscripteur_france():
    """
    Convention collaboration France — forfait par tranche de pages.
    Priorités décroissantes : la tranche la plus haute est évaluée en premier.
    """
    tranches = [
        (91, Decimal("500.00"), 10),
        (81, Decimal("450.00"), 20),
        (71, Decimal("400.00"), 30),
        (61, Decimal("350.00"), 40),
        (51, Decimal("300.00"), 50),
        (41, Decimal("250.00"), 60),
        (31, Decimal("200.00"), 70),
        (21, Decimal("150.00"), 80),
        (10, Decimal("100.00"), 90),
    ]
    regles = []
    for pages_min, montant, prio in tranches:
        regles.append({
            "libelle": f"Forfait retranscripteur France ≥ {pages_min} pages → {montant} €",
            "type_regle": TypeRegleEnum.BASE,
            "condition_type": ConditionTypeEnum.SI_VOLUME,
            "condition_valeur": {"pages_min": pages_min},
            "mode_calcul": ModeCalculEnum.FORFAIT_FIXE,
            "valeur": montant,
            "unite": "€",
            "priorite": prio,
        })
    # Tranche plancher : 1–9 pages (condition TOUJOURS, priorité la plus haute numériquement)
    regles.append({
        "libelle": "Forfait retranscripteur France 1–9 pages → 50 €",
        "type_regle": TypeRegleEnum.BASE,
        "condition_type": ConditionTypeEnum.TOUJOURS,
        "condition_valeur": None,
        "mode_calcul": ModeCalculEnum.FORFAIT_FIXE,
        "valeur": Decimal("50.00"),
        "unite": "€",
        "priorite": 100,
    })
    return regles


def _regles_retranscripteur_togo():
    """
    Convention collaboration Togo — forfait par tranche de pages (tarifs réduits).
    """
    tranches = [
        (81, Decimal("350.00"), 10),
        (61, Decimal("250.00"), 20),
        (51, Decimal("150.00"), 30),
        (41, Decimal("125.00"), 40),
        (31, Decimal("100.00"), 50),
        (21, Decimal("75.00"),  60),
        (10, Decimal("50.00"),  70),
    ]
    regles = []
    for pages_min, montant, prio in tranches:
        regles.append({
            "libelle": f"Forfait retranscripteur Togo ≥ {pages_min} pages → {montant} €",
            "type_regle": TypeRegleEnum.BASE,
            "condition_type": ConditionTypeEnum.SI_VOLUME,
            "condition_valeur": {"pages_min": pages_min},
            "mode_calcul": ModeCalculEnum.FORFAIT_FIXE,
            "valeur": montant,
            "unite": "€",
            "priorite": prio,
        })
    regles.append({
        "libelle": "Forfait retranscripteur Togo 1–9 pages → 25 €",
        "type_regle": TypeRegleEnum.BASE,
        "condition_type": ConditionTypeEnum.TOUJOURS,
        "condition_valeur": None,
        "mode_calcul": ModeCalculEnum.FORFAIT_FIXE,
        "valeur": Decimal("25.00"),
        "unite": "€",
        "priorite": 80,
    })
    return regles


# ── Définition de toutes les grilles ─────────────────────────────────────────

GRILLES = [
    # ── Grille client (inchangée) ──────────────────────────────────────────
    {
        "nom": "Tarif client standard",
        "type": TypeGrilleEnum.CLIENT,
        "cible": CibleGrilleEnum.GLOBAL,
        "version": "2.0",
        "active": True,
        "description": (
            "Grille de facturation client. "
            "Le forfait réel est calculé par tranche dans le code (_forfait_a2c). "
            "Ce taux moyen (5 €/page) sert de référence moteur pour les ajustements."
        ),
        "regles": [
            {
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

    # ── Retranscripteur France (remplace le placeholder 0.25 €/page) ───────
    {
        "nom": "Tarif retranscripteur France",
        "type": TypeGrilleEnum.RETRANSCRIPTEUR,
        "cible": CibleGrilleEnum.GLOBAL,
        "version": "2025.1",
        "active": True,
        "description": (
            "Convention collaboration France — tarifs signés. "
            "Forfait par tranche : 50 € (1–9 p) à 500 € (91–100 p). "
            "Grille globale par défaut pour tous les retranscripteurs."
        ),
        "regles": _regles_retranscripteur_france(),
        # Désactiver l'ancienne grille placeholder si elle existe
        "deactivate_old": "Tarif retranscripteur standard",
    },

    # ── Retranscripteur Togo (inactive par défaut, à assigner manuellement) ─
    {
        "nom": "Tarif retranscripteur Togo",
        "type": TypeGrilleEnum.RETRANSCRIPTEUR,
        "cible": CibleGrilleEnum.PRESTATAIRE_SPECIFIQUE,
        "version": "2025.1",
        "active": False,
        "description": (
            "Convention collaboration Togo — tarifs réduits signés. "
            "Forfait par tranche : 25 € (1–9 p) à 350 € (81–100 p). "
            "Inactive par défaut. Pour l'assigner à un prestataire basé au Togo : "
            "1) Activer cette grille, 2) Définir cible=prestataire_specifique + cible_id."
        ),
        "regles": _regles_retranscripteur_togo(),
    },

    # ── Correcteur standard (inchangé) ────────────────────────────────────
    {
        "nom": "Tarif correcteur standard",
        "type": TypeGrilleEnum.CORRECTEUR,
        "cible": CibleGrilleEnum.GLOBAL,
        "version": "1.0",
        "active": True,
        "description": (
            "Grille correcteur — taux provisoire 0.12 €/page. "
            "Les modalités A2C ne précisent pas de tarif correcteur séparé. "
            "À ajuster via l'interface selon les conventions signées."
        ),
        "regles": [
            {
                "libelle": "Tarif de base correcteur (provisoire)",
                "type_regle": TypeRegleEnum.BASE,
                "condition_type": ConditionTypeEnum.TOUJOURS,
                "mode_calcul": ModeCalculEnum.PAR_PAGE,
                "valeur": Decimal("0.12"),
                "unite": "€/page",
                "priorite": 10,
            },
        ],
    },

    # ── Majoration urgence (inchangée) ────────────────────────────────────
    {
        "nom": "Majoration urgence",
        "type": TypeGrilleEnum.URGENCE,
        "cible": CibleGrilleEnum.GLOBAL,
        "version": "1.0",
        "active": True,
        "description": "Majoration +30 % appliquée sur le montant client en cas d'urgence.",
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


# ── Fonctions utilitaires ─────────────────────────────────────────────────────

def _deactivate_by_name(db, nom: str, type_grille: TypeGrilleEnum) -> None:
    old = db.query(GrilleTarifaire).filter(
        GrilleTarifaire.nom == nom,
        GrilleTarifaire.type == type_grille,
        GrilleTarifaire.active == True,
    ).first()
    if old:
        old.active = False
        db.flush()
        print(f"  ⚠  Grille désactivée (remplacée) : {old.nom}")


def seed_grilles():
    db = SessionLocal()
    try:
        created = 0
        skipped = 0

        for spec in GRILLES:
            existing = db.query(GrilleTarifaire).filter(
                GrilleTarifaire.nom == spec["nom"],
                GrilleTarifaire.type == spec["type"],
            ).first()

            if existing:
                print(f"  → Déjà existante (ignorée) : {spec['nom']}")
                skipped += 1
                continue

            # Désactivation de l'ancienne grille si indiqué
            if "deactivate_old" in spec:
                _deactivate_by_name(db, spec["deactivate_old"], spec["type"])

            grille = GrilleTarifaire(
                nom=spec["nom"],
                type=spec["type"],
                cible=spec["cible"],
                version=spec["version"],
                date_debut=date.today(),
                active=spec.get("active", True),
                description=spec.get("description"),
            )
            db.add(grille)
            db.flush()

            for r in spec["regles"]:
                regle = RegleTarifaire(
                    grille_id=grille.id,
                    libelle=r["libelle"],
                    type_regle=r["type_regle"],
                    condition_type=r["condition_type"],
                    condition_valeur=r.get("condition_valeur"),
                    mode_calcul=r["mode_calcul"],
                    valeur=r["valeur"],
                    unite=r.get("unite"),
                    priorite=r.get("priorite", 100),
                    cumulable=True,
                    actif=True,
                )
                db.add(regle)

            db.commit()
            status = "✓" if spec.get("active", True) else "○ (inactive)"
            print(f"  {status} Grille créée : {spec['nom']} v{spec['version']}")
            created += 1

        print(f"\nSeed grilles terminé. {created} créée(s), {skipped} ignorée(s).")
        if created > 0:
            print("\nNOTE : Pour activer la grille Togo sur un prestataire spécifique :")
            print("  1. Ouvrir 'Tarif retranscripteur Togo' dans Grilles tarifaires")
            print("  2. Activer la grille + définir cible_id = UUID du prestataire")

    finally:
        db.close()


if __name__ == "__main__":
    seed_grilles()
