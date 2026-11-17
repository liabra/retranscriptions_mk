/**
 * Visites guidées de l'interface. Chaque étape peut changer de page (`route`) et
 * mettre en évidence un élément marqué `data-tour="<target>"`. Sans cible visible
 * (écran étroit, liste vide…), la bulle s'affiche au centre : la visite reste lisible.
 */
export interface TourStep {
  title: string
  body: string
  tip?: string
  route?: string
  target?: string
  /** Étape affichée seulement si l'utilisateur a au moins une de ces permissions */
  perms?: string[]
}

export interface Tour {
  id: string
  titre: string
  duree: string
  steps: TourStep[]
}

export const TOURS: Record<string, Tour> = {
  interface: {
    id: 'interface',
    titre: "Visite de l'interface",
    duree: '2 min',
    steps: [
      {
        route: '/tableau-de-bord',
        title: 'Bienvenue sur A2C Retranscriptions',
        body: "Cette visite vous montre où se trouve chaque fonction. Vous pouvez la quitter à tout moment avec Échap, et la relancer depuis la page Aide.",
        tip: 'Utilisez les flèches ← → du clavier pour avancer plus vite.',
      },
      {
        route: '/tableau-de-bord', target: 'kpi-production',
        title: 'Votre activité en un coup d’œil',
        body: 'Chaque indicateur compte les dossiers à une étape : audios à traiter, missions à attribuer, PV à relire, retards… Cliquez sur une tuile pour ouvrir la liste correspondante.',
        tip: 'La tuile « Dossiers en retard » passe en rouge dès qu’une échéance est dépassée : commencez votre journée par elle.',
      },
      {
        route: '/tableau-de-bord', target: 'kpi-finance', perms: ['finance.voir'],
        title: 'Facturation et règlements',
        body: 'Factures à établir, encaissements attendus et paiements des retranscripteurs sont suivis séparément de la production.',
      },
      {
        target: 'notifications',
        title: 'Notifications',
        body: 'La cloche signale les événements importants : PV livré, correction déposée, retard, facture créée… Un clic ouvre directement le dossier concerné.',
        tip: 'Les notifications fonctionnent même sans emails. Vous pourrez activer l’envoi par email plus tard dans « Mon compte ».',
      },
      {
        route: '/audios', target: 'audios-ajout', perms: ['audios.gerer'],
        title: 'Réception des audios',
        body: 'Tout commence ici : ajoutez un lien de partage OneDrive ou déposez le fichier audio, puis créez la mission en un clic.',
        tip: 'Le lien OneDrive est chiffré et n’est jamais montré aux retranscripteurs : ils téléchargent l’audio via la plateforme.',
      },
      {
        route: '/audios', target: 'audios-detection', perms: ['audios.gerer'],
        title: 'Détection automatique',
        body: 'Une fois OneDrive relié à la plateforme, les nouveaux audios déposés dans le dossier surveillé apparaîtront ici automatiquement.',
      },
      {
        route: '/dossiers', target: 'dossiers-filtres', perms: ['dossiers.voir'],
        title: 'Tous vos dossiers',
        body: 'Filtrez par étape (à qualifier, en retranscription, à relire, validés…), par retard ou par urgence, et recherchez une référence ou un titre.',
      },
      {
        route: '/dossiers', target: 'dossier-nouveau', perms: ['dossiers.gerer'],
        title: 'Créer un dossier',
        body: 'Vous pouvez aussi créer un dossier sans audio. L’échéance client est calculée automatiquement à partir de la date de réception de l’audio et des délais paramétrés.',
        tip: 'Dans la fiche d’un dossier, le bouton « Guide de cette page » explique chaque zone.',
      },
      {
        route: '/finance', target: 'finance-onglets', perms: ['finance.voir'],
        title: 'Facturation & règlements',
        body: 'Cinq onglets : factures à établir, en attente de règlement, réglées, paiements des retranscripteurs à effectuer, et effectués.',
      },
      {
        route: '/tarifs', target: 'tarifs-onglets', perms: ['tarifs.gerer', 'finance.voir'],
        title: 'Tarifs et paramètres',
        body: 'Barèmes clients, rémunérations, majorations, délais de réalisation et simulateur. Chaque modification crée une nouvelle version datée.',
        tip: 'Préparez le barème de l’année suivante avec le bouton « Barème » : il s’appliquera aux audios reçus à partir du 1er janvier.',
      },
      {
        route: '/retranscripteurs', target: 'retranscripteurs-nouveau', perms: ['prestataires.gerer'],
        title: 'Vos retranscripteurs',
        body: 'Créez une fiche, puis l’accès du retranscripteur : un mot de passe temporaire s’affiche une seule fois, à lui transmettre par téléphone ou SMS.',
      },
      {
        route: '/utilisateurs', target: 'utilisateurs-nouveau', perms: ['utilisateurs.gerer'],
        title: 'Utilisateurs & droits',
        body: 'Gérez les comptes de l’équipe et ajustez les droits de la coordinatrice. Vous pouvez aussi remplacer une adresse de connexion par la vraie adresse.',
      },
      {
        route: '/aide', target: 'guide-parcours',
        title: 'Pour aller plus loin',
        body: 'Le parcours de démonstration suit un PV fictif de la réception de l’audio jusqu’à la facture réglée. Rien n’y est enregistré : vous pouvez le refaire autant de fois que vous voulez.',
      },
    ],
  },

  dossier: {
    id: 'dossier',
    titre: 'Guide de la fiche dossier',
    duree: '1 min',
    steps: [
      {
        target: 'dossier-statuts',
        title: 'Deux suivis distincts',
        body: 'Le premier badge indique l’étape de production du PV, le second l’état de la facturation. Le paiement du retranscripteur est suivi dans l’onglet Facturation.',
      },
      {
        target: 'dossier-frise',
        title: 'La frise d’avancement',
        body: 'Elle montre où en est le dossier : qualification, attribution, retranscription, PV reçu, relecture, contrôle, validation.',
      },
      {
        target: 'dossier-action',
        title: 'La prochaine étape',
        body: 'Ce cadre vous propose toujours l’action à faire maintenant : qualifier, attribuer, commencer la relecture, valider…',
        tip: 'Si rien n’est à faire de votre côté, le cadre indique qui doit agir et pour quand.',
      },
      {
        target: 'dossier-onglets',
        title: 'Tout le dossier en onglets',
        body: 'Aperçu (infos, audio, échéance), Versions du PV (contrôle de conformité, comparaison), Attribution (suggestions), Facturation et Historique (qui a fait quoi, quand).',
      },
    ],
  },

  prestataire: {
    id: 'prestataire',
    titre: 'Découvrir mon espace',
    duree: '1 min',
    steps: [
      {
        route: '/mes-missions',
        title: 'Bienvenue dans votre espace',
        body: 'Vous y trouvez uniquement les missions qui vous sont confiées, triées par échéance.',
      },
      {
        route: '/mes-missions', target: 'missions-onglets',
        title: 'En cours et terminées',
        body: 'L’onglet « Terminées » garde la trace de vos missions validées.',
      },
      {
        route: '/mes-missions', target: 'mission-carte',
        title: 'Une carte par mission',
        body: '1. Téléchargez l’audio. 2. Déposez votre PV au format Word (.docx), en Comic Sans MS taille 12. Un contrôle automatique vous indique tout de suite si la mise en forme est conforme.',
        tip: 'Si une correction est demandée, le message apparaît sur la carte : déposez simplement la nouvelle version.',
      },
      {
        target: 'notifications',
        title: 'Restez informé(e)',
        body: 'La cloche vous prévient d’une nouvelle mission, d’une correction demandée ou d’une échéance proche.',
      },
    ],
  },
}

export function tourPourRole(isPrestataire: boolean, isClient: boolean): string | null {
  if (isClient) return null
  return isPrestataire ? 'prestataire' : 'interface'
}
