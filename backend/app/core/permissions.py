"""
Permissions fonctionnelles.

L'administratrice possède toutes les permissions. Les autres rôles internes ont des
permissions par défaut que l'administratrice peut ajuster utilisateur par utilisateur
(colonne users.permissions : {"finance.gerer": true, ...}).
Les prestataires et clients n'ont aucune permission interne : ils utilisent
exclusivement leurs espaces dédiés, contrôlés par affectation / propriété.
"""
from typing import Dict, FrozenSet, Set

from app.models.user import RoleEnum, User

PERMISSIONS: Dict[str, str] = {
    "dossiers.voir": "Consulter les dossiers et leur suivi",
    "dossiers.gerer": "Créer, qualifier, bloquer et archiver les dossiers",
    "audios.gerer": "Enregistrer et qualifier les audios",
    "attribution.gerer": "Attribuer les missions aux retranscripteurs",
    "relecture": "Relire les PV et demander des corrections",
    "validation": "Valider définitivement les PV",
    "prestataires.gerer": "Gérer les fiches retranscripteurs",
    "prestataires.performance": "Consulter les indicateurs de performance",
    "clients.gerer": "Gérer les clients et instances",
    "finance.voir": "Consulter tarifs calculés, factures et règlements",
    "finance.gerer": "Établir les factures, encaissements et paiements",
    "tarifs.gerer": "Gérer les tarifs, majorations et délais (paramètres commerciaux)",
    "journal.voir": "Consulter le journal d'activité",
}

# Jamais délégables : réservées à l'administratrice
ADMIN_ONLY: FrozenSet[str] = frozenset({"utilisateurs.gerer", "iban.voir"})

INTERNAL_ROLES: FrozenSet[RoleEnum] = frozenset({
    RoleEnum.ADMINISTRATRICE, RoleEnum.COORDINATRICE, RoleEnum.COMPTABILITE, RoleEnum.LECTURE_SEULE,
})
PRESTATAIRE_ROLES: FrozenSet[RoleEnum] = frozenset({RoleEnum.RETRANSCRIPTEUR, RoleEnum.CORRECTEUR})

DEFAULTS: Dict[RoleEnum, Set[str]] = {
    RoleEnum.COORDINATRICE: {
        "dossiers.voir", "dossiers.gerer", "audios.gerer", "attribution.gerer",
        "relecture", "validation", "prestataires.performance", "journal.voir", "clients.gerer",
    },
    RoleEnum.COMPTABILITE: {"dossiers.voir", "finance.voir", "finance.gerer"},
    RoleEnum.LECTURE_SEULE: {"dossiers.voir"},
}


def effective_permissions(user: User) -> Set[str]:
    if user.role == RoleEnum.ADMINISTRATRICE:
        return set(PERMISSIONS) | set(ADMIN_ONLY)
    if user.role not in INTERNAL_ROLES:
        return set()
    perms = set(DEFAULTS.get(user.role, set()))
    for name, granted in (user.permissions or {}).items():
        if name not in PERMISSIONS:
            continue  # fix: ignore toute clé inconnue ou réservée admin
        if granted:
            perms.add(name)
        else:
            perms.discard(name)
    return perms


def has_permission(user: User, perm: str) -> bool:
    return perm in effective_permissions(user)


def is_internal(user: User) -> bool:
    return user.role in INTERNAL_ROLES
