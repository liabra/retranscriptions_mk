"""
Machine d'états de la refonte — trois suivis indépendants :

1. Production du PV          → dossiers.statut_production
2. Facturation / encaissement → dossiers.statut_facturation
3. Paiement prestataire       → paiements_prestataires.statut (a_payer → valide → paye)

Toute modification de statut passe par ce module (aucune affectation directe ailleurs).
Le statut historique `dossiers.statut` est maintenu en cohérence pour compatibilité.
"""
import uuid
from typing import Dict, Optional, Set

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.dossier import Dossier, StatutDossierEnum
from app.models.journal import TypeActionEnum
from app.services.journal import log_action

# ── Production ────────────────────────────────────────────────────────────────
A_QUALIFIER = "a_qualifier"
A_ATTRIBUER = "a_attribuer"
ATTRIBUE = "attribue"
EN_COURS = "en_cours"
LIVRE = "livre"
A_RELIRE = "a_relire"
CORRECTION_DEMANDEE = "correction_demandee"
A_CONTROLER = "a_controler"
VALIDE = "valide"
ARCHIVE = "archive"
BLOQUE = "bloque"

PRODUCTION_LABELS: Dict[str, str] = {
    A_QUALIFIER: "À qualifier",
    A_ATTRIBUER: "À attribuer",
    ATTRIBUE: "Attribué",
    EN_COURS: "En cours",
    LIVRE: "Livré",
    A_RELIRE: "À relire",
    CORRECTION_DEMANDEE: "Correction demandée",
    A_CONTROLER: "À contrôler",
    VALIDE: "Validé",
    ARCHIVE: "Archivé",
    BLOQUE: "Bloqué",
}

PRODUCTION_TRANSITIONS: Dict[str, Set[str]] = {
    A_QUALIFIER: {A_ATTRIBUER, BLOQUE},
    A_ATTRIBUER: {ATTRIBUE, A_QUALIFIER, BLOQUE},
    ATTRIBUE: {EN_COURS, LIVRE, A_ATTRIBUER, BLOQUE},
    EN_COURS: {LIVRE, A_ATTRIBUER, BLOQUE},
    LIVRE: {A_RELIRE, LIVRE, BLOQUE},
    A_RELIRE: {CORRECTION_DEMANDEE, A_CONTROLER, LIVRE, BLOQUE},
    CORRECTION_DEMANDEE: {LIVRE, A_ATTRIBUER, BLOQUE},
    A_CONTROLER: {VALIDE, CORRECTION_DEMANDEE, A_RELIRE, LIVRE, BLOQUE},
    VALIDE: {ARCHIVE},
    ARCHIVE: set(),
    BLOQUE: set(),  # le déblocage restaure le statut précédent (voir debloquer)
}

ACTIFS = {A_QUALIFIER, A_ATTRIBUER, ATTRIBUE, EN_COURS, LIVRE, A_RELIRE, CORRECTION_DEMANDEE, A_CONTROLER}
EN_PRODUCTION = {ATTRIBUE, EN_COURS, CORRECTION_DEMANDEE}

# Correspondance vers l'ancien statut (compatibilité, rapports existants)
_LEGACY: Dict[str, StatutDossierEnum] = {
    A_QUALIFIER: StatutDossierEnum.RECU,
    A_ATTRIBUER: StatutDossierEnum.A_ATTRIBUER,
    ATTRIBUE: StatutDossierEnum.EN_RETRANSCRIPTION,
    EN_COURS: StatutDossierEnum.EN_RETRANSCRIPTION,
    LIVRE: StatutDossierEnum.A_CORRIGER,
    A_RELIRE: StatutDossierEnum.EN_CORRECTION,
    CORRECTION_DEMANDEE: StatutDossierEnum.EN_CORRECTION,
    A_CONTROLER: StatutDossierEnum.A_VALIDER,
    VALIDE: StatutDossierEnum.ENVOYE,
    ARCHIVE: StatutDossierEnum.ARCHIVE,
    BLOQUE: StatutDossierEnum.BLOQUE,
}

# Sens inverse : reprise des dossiers existants (migration 0005)
LEGACY_TO_PRODUCTION: Dict[str, str] = {
    "recu": A_QUALIFIER, "en_qualification": A_QUALIFIER, "incomplet": A_QUALIFIER,
    "estime": A_ATTRIBUER, "a_attribuer": A_ATTRIBUER,
    "en_retranscription": EN_COURS,
    "a_corriger": LIVRE, "en_correction": A_RELIRE, "en_mise_en_forme": A_RELIRE,
    "calcul_en_cours": A_CONTROLER, "a_valider": A_CONTROLER,
    "envoye": VALIDE, "facture": VALIDE, "paye_entrant": VALIDE, "prestataires_payes": VALIDE,
    "archive": ARCHIVE, "bloque": BLOQUE,
}

# ── Facturation ───────────────────────────────────────────────────────────────
F_NON_APPLICABLE = "non_applicable"
F_A_ETABLIR = "a_etablir"
F_EMISE = "emise"
F_PARTIELLE = "partiellement_reglee"
F_REGLEE = "reglee"

FACTURATION_LABELS: Dict[str, str] = {
    F_NON_APPLICABLE: "Pas encore facturable",
    F_A_ETABLIR: "Facture à établir",
    F_EMISE: "Facture émise",
    F_PARTIELLE: "Partiellement réglée",
    F_REGLEE: "Réglée",
}

FACTURATION_TRANSITIONS: Dict[str, Set[str]] = {
    F_NON_APPLICABLE: {F_A_ETABLIR},
    F_A_ETABLIR: {F_EMISE},
    F_EMISE: {F_PARTIELLE, F_REGLEE, F_A_ETABLIR},   # retour à établir = facture annulée
    F_PARTIELLE: {F_REGLEE, F_PARTIELLE},
    F_REGLEE: set(),
}

# ── Paiement prestataire ──────────────────────────────────────────────────────
PAIEMENT_TRANSITIONS: Dict[str, Set[str]] = {
    "a_payer": {"valide"},
    "valide": {"paye", "a_payer"},
    "paye": set(),
}


def _deny(kind: str, current: str, target: str, allowed: Set[str]) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail=f"Transition {kind} « {current} » → « {target} » non autorisée"
               + (f" (possibles : {', '.join(sorted(allowed))})" if allowed else ""),
    )


def changer_production(
    db: Session, dossier: Dossier, cible: str, user_id: Optional[uuid.UUID],
    motif: Optional[str] = None, extra: Optional[dict] = None,
) -> None:
    actuel = dossier.statut_production
    autorises = PRODUCTION_TRANSITIONS.get(actuel, set())
    if cible not in autorises:
        raise _deny("de production", actuel, cible, autorises)
    _appliquer(db, dossier, actuel, cible, user_id, motif, extra)


def _appliquer(db, dossier, actuel, cible, user_id, motif, extra):
    dossier.statut_production = cible
    dossier.statut = _LEGACY[cible]
    detail = {"suivi": "production", "ancien": actuel, "nouveau": cible}
    if motif:
        detail["motif"] = motif[:1000]
    if extra:
        detail.update(extra)
    log_action(db, TypeActionEnum.STATUT, dossier_id=dossier.id, utilisateur_id=user_id, detail=detail)


def bloquer(db: Session, dossier: Dossier, user_id: uuid.UUID, motif: str) -> None:
    actuel = dossier.statut_production
    if BLOQUE not in PRODUCTION_TRANSITIONS.get(actuel, set()):
        raise _deny("de production", actuel, BLOQUE, PRODUCTION_TRANSITIONS.get(actuel, set()))
    dossier.statut_avant_blocage = actuel
    dossier.motif_blocage = motif
    _appliquer(db, dossier, actuel, BLOQUE, user_id, motif, None)


def debloquer(db: Session, dossier: Dossier, user_id: uuid.UUID) -> None:
    if dossier.statut_production != BLOQUE:
        raise HTTPException(status_code=409, detail="Ce dossier n'est pas bloqué")
    retour = dossier.statut_avant_blocage if dossier.statut_avant_blocage in ACTIFS else A_QUALIFIER
    dossier.statut_avant_blocage = None
    dossier.motif_blocage = None
    _appliquer(db, dossier, BLOQUE, retour, user_id, "déblocage", None)


def changer_facturation(
    db: Session, dossier: Dossier, cible: str, user_id: Optional[uuid.UUID], motif: Optional[str] = None,
) -> None:
    actuel = dossier.statut_facturation
    autorises = FACTURATION_TRANSITIONS.get(actuel, set())
    if cible not in autorises:
        raise _deny("de facturation", actuel, cible, autorises)
    dossier.statut_facturation = cible
    detail = {"suivi": "facturation", "ancien": actuel, "nouveau": cible}
    if motif:
        detail["motif"] = motif[:1000]
    log_action(db, TypeActionEnum.PAIEMENT, dossier_id=dossier.id, utilisateur_id=user_id, detail=detail)


def verifier_paiement(actuel: str, cible: str) -> None:
    autorises = PAIEMENT_TRANSITIONS.get(actuel, set())
    if cible not in autorises:
        raise _deny("de paiement", actuel, cible, autorises)
