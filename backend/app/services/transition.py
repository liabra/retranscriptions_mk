"""
Moteur de transitions de statut pour les dossiers.
Chaque transition est validée : impossible de sauter des étapes sans règle.
"""
from typing import Set, Dict
from app.models.dossier import StatutDossierEnum

# Graphe des transitions autorisées
# clé = statut source, valeur = ensemble des statuts cibles autorisés
TRANSITIONS_AUTORISEES: Dict[StatutDossierEnum, Set[StatutDossierEnum]] = {
    StatutDossierEnum.RECU: {
        StatutDossierEnum.EN_QUALIFICATION,
        StatutDossierEnum.BLOQUE,
        StatutDossierEnum.INCOMPLET,
    },
    StatutDossierEnum.EN_QUALIFICATION: {
        StatutDossierEnum.ESTIME,
        StatutDossierEnum.BLOQUE,
        StatutDossierEnum.INCOMPLET,
    },
    StatutDossierEnum.ESTIME: {
        StatutDossierEnum.A_ATTRIBUER,
        StatutDossierEnum.BLOQUE,
    },
    StatutDossierEnum.A_ATTRIBUER: {
        StatutDossierEnum.EN_RETRANSCRIPTION,
        StatutDossierEnum.BLOQUE,
    },
    StatutDossierEnum.EN_RETRANSCRIPTION: {
        StatutDossierEnum.A_CORRIGER,
        StatutDossierEnum.BLOQUE,
    },
    StatutDossierEnum.A_CORRIGER: {
        StatutDossierEnum.EN_CORRECTION,
        StatutDossierEnum.BLOQUE,
    },
    StatutDossierEnum.EN_CORRECTION: {
        StatutDossierEnum.EN_MISE_EN_FORME,
        StatutDossierEnum.BLOQUE,
    },
    StatutDossierEnum.EN_MISE_EN_FORME: {
        StatutDossierEnum.A_VALIDER,
        StatutDossierEnum.BLOQUE,
    },
    StatutDossierEnum.A_VALIDER: {
        StatutDossierEnum.ENVOYE,
        StatutDossierEnum.EN_MISE_EN_FORME,  # retour pour corrections
        StatutDossierEnum.BLOQUE,
    },
    StatutDossierEnum.ENVOYE: {
        StatutDossierEnum.ARCHIVE,
        StatutDossierEnum.FACTURE,  # compatible avec le module finance futur
    },
    StatutDossierEnum.FACTURE: {
        StatutDossierEnum.PAYE_ENTRANT,
    },
    StatutDossierEnum.PAYE_ENTRANT: {
        StatutDossierEnum.PRESTATAIRES_PAYES,
    },
    StatutDossierEnum.PRESTATAIRES_PAYES: {
        StatutDossierEnum.ARCHIVE,
    },
    StatutDossierEnum.BLOQUE: {
        # Depuis BLOQUE, retour possible vers les états actifs (déblocage manuel)
        StatutDossierEnum.RECU,
        StatutDossierEnum.EN_QUALIFICATION,
        StatutDossierEnum.ESTIME,
        StatutDossierEnum.A_ATTRIBUER,
        StatutDossierEnum.EN_RETRANSCRIPTION,
        StatutDossierEnum.A_CORRIGER,
        StatutDossierEnum.EN_CORRECTION,
        StatutDossierEnum.EN_MISE_EN_FORME,
        StatutDossierEnum.A_VALIDER,
    },
    StatutDossierEnum.INCOMPLET: {
        StatutDossierEnum.RECU,
        StatutDossierEnum.EN_QUALIFICATION,
    },
    # États terminaux
    StatutDossierEnum.ARCHIVE: set(),
}


def transition_autorisee(statut_actuel: StatutDossierEnum, statut_cible: StatutDossierEnum) -> bool:
    """Retourne True si la transition est autorisée."""
    return statut_cible in TRANSITIONS_AUTORISEES.get(statut_actuel, set())


def transitions_disponibles(statut_actuel: StatutDossierEnum) -> Set[StatutDossierEnum]:
    """Retourne l'ensemble des transitions possibles depuis un statut donné."""
    return TRANSITIONS_AUTORISEES.get(statut_actuel, set())
