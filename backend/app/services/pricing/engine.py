"""
Moteur de tarification — service Python pur, indépendant, testable unitairement.

PRINCIPE CARDINAL : Aucune valeur tarifaire n'est codée en dur ici.
Toutes les règles et montants viennent de la base de données (GrilleTarifaire + RegleTarifaire).

Le moteur calcule DEUX montants distincts et indépendants :
  → Montant CLIENT : ce qui est facturé (grille client + majorations)
  → Montant PRESTATAIRES : ce qui est payé (grille prestataire x rôle + majorations)

Étapes à chaque calcul :
  1. Collecte des critères du dossier
  2. Sélection des règles actives dans l'ordre de priorité
  3. Application des règles sur la base de calcul (nombre de pages)
  4. Production d'un objet CalculTarifaire traçable

TODO Phase 4 : Implémenter run_calcul() complet.
              Cette architecture est prête — les modèles sont en place.
"""
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.models.pricing.grille import GrilleTarifaire, TypeGrilleEnum, CibleGrilleEnum
from app.models.pricing.regle import RegleTarifaire, TypeRegleEnum, ModeCalculEnum
from app.models.pricing.calcul import CalculTarifaire, StatutCalculEnum
from app.models.dossier import Dossier


@dataclass
class CriteresDossier:
    """Critères extraits du dossier pour alimenter le moteur."""
    type_instance: str
    urgence: bool
    sans_prise_de_note: bool
    prestation_speciale: bool
    type_prestation_speciale: Optional[str]
    nombre_pages: Decimal
    client_id: uuid.UUID
    # Prestataires attribués (peuvent avoir grilles spécifiques)
    retranscripteur_id: Optional[uuid.UUID] = None
    correcteur_id: Optional[uuid.UUID] = None


@dataclass
class LigneCalcul:
    """Résultat d'application d'une règle — pour la traçabilité."""
    regle_id: str
    regle_libelle: str
    grille_id: str
    grille_version: str
    condition_evaluee: Dict[str, Any]
    valeur_appliquee: str
    impact_montant: Decimal
    cible: str  # "CLIENT" | "PRESTATAIRE" | "LES_DEUX"
    ordre_application: int


@dataclass
class ResultatCalcul:
    """Objet retourné par le moteur avant persistance."""
    nombre_pages: Decimal
    criteres: Dict[str, Any]
    lignes: List[LigneCalcul] = field(default_factory=list)

    montant_client_brut: Decimal = Decimal("0.00")
    montant_retranscripteur: Decimal = Decimal("0.00")
    montant_correcteur: Decimal = Decimal("0.00")

    @property
    def montant_prestataires_total(self) -> Decimal:
        return self.montant_retranscripteur + self.montant_correcteur

    @property
    def marge_brute(self) -> Decimal:
        return self.montant_client_brut - self.montant_prestataires_total


class PricingEngine:
    """
    Service de calcul tarifaire.
    Instancier avec une session DB, appeler run_calcul().
    """

    def __init__(self, db: Session):
        self.db = db

    def _get_active_grille(
        self,
        type_grille: TypeGrilleEnum,
        cible_id: Optional[uuid.UUID] = None,
    ) -> Optional[GrilleTarifaire]:
        """
        Sélectionne la grille active applicable.
        Règle de priorité : grille spécifique > grille standard.
        """
        from datetime import date
        today = date.today()

        # 1. Cherche grille spécifique si cible_id fourni
        if cible_id:
            specific = (
                self.db.query(GrilleTarifaire)
                .filter(
                    GrilleTarifaire.type == type_grille,
                    GrilleTarifaire.cible != CibleGrilleEnum.GLOBAL,
                    GrilleTarifaire.cible_id == cible_id,
                    GrilleTarifaire.active == True,
                    GrilleTarifaire.date_debut <= today,
                )
                .filter(
                    (GrilleTarifaire.date_fin == None) | (GrilleTarifaire.date_fin >= today)
                )
                .first()
            )
            if specific:
                return specific

        # 2. Grille standard globale
        return (
            self.db.query(GrilleTarifaire)
            .filter(
                GrilleTarifaire.type == type_grille,
                GrilleTarifaire.cible == CibleGrilleEnum.GLOBAL,
                GrilleTarifaire.active == True,
                GrilleTarifaire.date_debut <= today,
            )
            .filter(
                (GrilleTarifaire.date_fin == None) | (GrilleTarifaire.date_fin >= today)
            )
            .first()
        )

    def _evaluate_condition(
        self, regle: RegleTarifaire, criteres: CriteresDossier
    ) -> bool:
        """Évalue si la condition d'une règle s'applique aux critères du dossier."""
        from app.models.pricing.regle import ConditionTypeEnum
        ct = regle.condition_type
        cv = regle.condition_valeur or {}

        if ct == ConditionTypeEnum.TOUJOURS:
            return True
        if ct == ConditionTypeEnum.SI_TYPE_INSTANCE:
            return criteres.type_instance == cv.get("type_instance")
        if ct == ConditionTypeEnum.SI_URGENCE:
            return criteres.urgence
        if ct == ConditionTypeEnum.SI_SNP:
            return criteres.sans_prise_de_note
        if ct == ConditionTypeEnum.SI_SPECIAL:
            return criteres.prestation_speciale
        if ct == ConditionTypeEnum.SI_VOLUME:
            seuil = Decimal(str(cv.get("pages_min", 0)))
            return criteres.nombre_pages >= seuil
        if ct == ConditionTypeEnum.COMBINEE:
            # Toutes les conditions doivent être vraies
            results = []
            if "urgence" in cv:
                results.append(criteres.urgence == cv["urgence"])
            if "type_instance" in cv:
                results.append(criteres.type_instance == cv["type_instance"])
            if "snp" in cv:
                results.append(criteres.sans_prise_de_note == cv["snp"])
            return all(results) if results else False
        return False

    def _apply_rule(
        self,
        regle: RegleTarifaire,
        current_amount: Decimal,
        base_amount: Decimal,
        nombre_pages: Decimal,
    ) -> Decimal:
        """Calcule l'impact d'une règle sur le montant courant."""
        v = regle.valeur
        if regle.mode_calcul == ModeCalculEnum.PAR_PAGE:
            impact = v * nombre_pages
        elif regle.mode_calcul == ModeCalculEnum.FORFAIT_FIXE:
            impact = v
        elif regle.mode_calcul == ModeCalculEnum.POURCENTAGE_BASE:
            impact = base_amount * (v / Decimal("100"))
        elif regle.mode_calcul == ModeCalculEnum.POURCENTAGE_TOTAL:
            impact = current_amount * (v / Decimal("100"))
        elif regle.mode_calcul == ModeCalculEnum.MULTIPLICATEUR:
            impact = current_amount * v - current_amount
        else:
            impact = Decimal("0.00")

        if regle.type_regle == TypeRegleEnum.REMISE:
            impact = -abs(impact)

        if regle.plafond_montant:
            impact = min(impact, regle.plafond_montant)

        return impact.quantize(Decimal("0.01"))

    def _calcul_cote(
        self,
        grilles: List[GrilleTarifaire],
        criteres: CriteresDossier,
        cible_label: str,
    ) -> tuple[Decimal, List[LigneCalcul]]:
        """
        Calcule un côté (CLIENT ou PRESTATAIRE) à partir d'une liste de grilles.
        Retourne (montant_brut, lignes_tracabilite).
        """
        # Collecte et trie toutes les règles actives applicables
        all_rules: List[RegleTarifaire] = []
        for grille in grilles:
            if grille:
                rules = (
                    self.db.query(RegleTarifaire)
                    .filter(
                        RegleTarifaire.grille_id == grille.id,
                        RegleTarifaire.actif == True,
                    )
                    .order_by(RegleTarifaire.priorite)
                    .all()
                )
                all_rules.extend(rules)

        # Trie global par priorité + type (BASE en premier)
        type_order = {TypeRegleEnum.BASE: 0, TypeRegleEnum.MAJORATION: 1,
                      TypeRegleEnum.REMISE: 2, TypeRegleEnum.FORFAIT: 3,
                      TypeRegleEnum.PLANCHER: 4, TypeRegleEnum.PLAFOND: 5}
        all_rules.sort(key=lambda r: (type_order.get(r.type_regle, 9), r.priorite))

        montant = Decimal("0.00")
        base_montant = Decimal("0.00")
        lignes: List[LigneCalcul] = []
        ordre = 0

        for regle in all_rules:
            if not self._evaluate_condition(regle, criteres):
                continue

            # Une seule règle BASE autorisée
            if regle.type_regle == TypeRegleEnum.BASE:
                if base_montant > 0:
                    continue  # déjà une BASE, on ignore

            impact = self._apply_rule(regle, montant, base_montant, criteres.nombre_pages)

            if regle.type_regle == TypeRegleEnum.BASE:
                base_montant = impact
                montant = impact
            elif regle.type_regle == TypeRegleEnum.PLANCHER:
                montant = max(montant, regle.valeur)
                impact = montant - (montant - impact)
            elif regle.type_regle == TypeRegleEnum.PLAFOND:
                montant = min(montant, regle.valeur)
                impact = Decimal("0.00")
            else:
                montant += impact

            grille_obj = next((g for g in grilles if g and regle.grille_id == g.id), None)
            lignes.append(LigneCalcul(
                regle_id=str(regle.id),
                regle_libelle=regle.libelle,
                grille_id=str(regle.grille_id),
                grille_version=grille_obj.version if grille_obj else "?",
                condition_evaluee={"type": regle.condition_type.value, "valeur": regle.condition_valeur},
                valeur_appliquee=f"{regle.valeur} {regle.unite or ''}".strip(),
                impact_montant=impact,
                cible=cible_label,
                ordre_application=ordre,
            ))
            ordre += 1

        return montant.quantize(Decimal("0.01")), lignes

    def run_calcul(
        self,
        dossier: Dossier,
        nombre_pages: Decimal,
        version: int = 1,
        utilisateur_id: Optional[uuid.UUID] = None,
    ) -> CalculTarifaire:
        """
        Calcul tarifaire complet — produit un CalculTarifaire persisté.
        """
        criteres_dict = dossier.criteres_tarif or {}
        criteres = CriteresDossier(
            type_instance=dossier.type_instance.value,
            urgence=dossier.est_urgent or criteres_dict.get("urgence", False),
            sans_prise_de_note=criteres_dict.get("sans_prise_de_note", False),
            prestation_speciale=criteres_dict.get("prestation_speciale", False),
            type_prestation_speciale=criteres_dict.get("type_prestation_speciale"),
            nombre_pages=nombre_pages,
            client_id=dossier.client_id,
        )

        # ── Côté CLIENT ─────────────────────────────────────────────────
        grille_client = self._get_active_grille(TypeGrilleEnum.CLIENT, criteres.client_id)
        grilles_client = [g for g in [grille_client] if g]
        if criteres.urgence:
            g_urg = self._get_active_grille(TypeGrilleEnum.URGENCE)
            if g_urg:
                grilles_client.append(g_urg)
        if criteres.sans_prise_de_note:
            g_snp = self._get_active_grille(TypeGrilleEnum.SNP)
            if g_snp:
                grilles_client.append(g_snp)
        if criteres.prestation_speciale:
            g_spe = self._get_active_grille(TypeGrilleEnum.SPECIAL)
            if g_spe:
                grilles_client.append(g_spe)

        montant_client, lignes_client = self._calcul_cote(grilles_client, criteres, "CLIENT")

        # ── Côté RETRANSCRIPTEUR ─────────────────────────────────────────
        grille_retrans = self._get_active_grille(
            TypeGrilleEnum.RETRANSCRIPTEUR, criteres.retranscripteur_id
        )
        grilles_retrans = [g for g in [grille_retrans] if g]
        if criteres.urgence:
            g_urg_p = self._get_active_grille(TypeGrilleEnum.URGENCE)
            if g_urg_p:
                grilles_retrans.append(g_urg_p)
        if criteres.sans_prise_de_note:
            g_snp_p = self._get_active_grille(TypeGrilleEnum.SNP)
            if g_snp_p:
                grilles_retrans.append(g_snp_p)

        montant_retrans, lignes_retrans = self._calcul_cote(grilles_retrans, criteres, "RETRANSCRIPTEUR")

        # ── Côté CORRECTEUR ──────────────────────────────────────────────
        grille_correcteur = self._get_active_grille(
            TypeGrilleEnum.CORRECTEUR, criteres.correcteur_id
        )
        grilles_correct = [g for g in [grille_correcteur] if g]
        montant_correct, lignes_correct = self._calcul_cote(grilles_correct, criteres, "CORRECTEUR")

        # ── Snapshot des grilles utilisées ───────────────────────────────
        grilles_snap = {}
        for g in set(filter(None, grilles_client + grilles_retrans + grilles_correct)):
            grilles_snap[str(g.id)] = {"nom": g.nom, "version": g.version, "type": g.type.value}

        # ── Persistance ──────────────────────────────────────────────────
        toutes_lignes = lignes_client + lignes_retrans + lignes_correct
        montant_presta_total = (montant_retrans + montant_correct).quantize(Decimal("0.01"))
        marge = (montant_client - montant_presta_total).quantize(Decimal("0.01"))

        calcul = CalculTarifaire(
            dossier_id=dossier.id,
            version_calcul=version,
            declenche_par_id=utilisateur_id,
            nombre_pages=nombre_pages,
            criteres_appliques=criteres_dict,
            regles_appliquees=[
                {
                    "regle_id": l.regle_id,
                    "regle_libelle": l.regle_libelle,
                    "grille_id": l.grille_id,
                    "grille_version": l.grille_version,
                    "condition_evaluee": l.condition_evaluee,
                    "valeur_appliquee": l.valeur_appliquee,
                    "impact_montant": str(l.impact_montant),
                    "cible": l.cible,
                    "ordre_application": l.ordre_application,
                }
                for l in toutes_lignes
            ],
            montant_client_brut=montant_client,
            ajustement_client=Decimal("0.00"),
            montant_client_final=montant_client,
            montant_retranscripteur=montant_retrans,
            montant_correcteur=montant_correct,
            montant_prestataires_total=montant_presta_total,
            marge_brute=marge,
            grilles_version_snap=grilles_snap,
            statut=StatutCalculEnum.ESTIMATIF if version == 1 else StatutCalculEnum.DEFINITIF,
        )

        self.db.add(calcul)
        self.db.flush()

        # Met à jour le pointeur du dossier
        dossier.calcul_tarifaire_id = calcul.id

        return calcul
