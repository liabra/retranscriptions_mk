/** Points d'accès de la refonte, typés. */
import { apiClient } from '@/services/api'

export type Role = 'administratrice' | 'coordinatrice' | 'retranscripteur' | 'correcteur' | 'comptabilite' | 'lecture_seule' | 'client'

export interface Me {
  id: string; email: string; nom: string; role: Role; actif: boolean; created_at: string
  last_login: string | null; must_change_password: boolean; notif_email: boolean
  prestataire_id: string | null; client_id: string | null; permissions: string[]
  permissions_personnalisees: Record<string, boolean> | null
}

export interface DossierResume {
  id: string; reference: string; titre: string | null; type_instance: string
  client_id: string; client_nom: string | null
  statut_production: string; statut_production_label: string
  statut_facturation: string; statut_facturation_label: string
  date_seance: string | null; date_limite: string | null; date_limite_rendu: string | null
  est_urgent: boolean; en_retard: boolean; duree_audio_minutes: number | null
  retranscripteur: { id: string; nom: string } | null
  created_at: string; updated_at: string
}

export interface Audio {
  id: string; nom_fichier: string; taille_octets: number | null; mime_type: string | null
  duree_minutes: number | null; origine: string; disponible: boolean; statut: string
  message_verification: string | null; verifie_le: string | null; created_at: string
  client_id: string | null; client_nom?: string | null; dossier_id: string | null
}

export interface Rapport {
  statut: string; resume: string; exigences: { police: string; taille_pt: number }
  caracteres_total: number; taux_conformite: number
  polices: Record<string, number>; tailles: Record<string, number>
  anomalies: { zone: string; paragraphe: number; extrait: string; problemes: string[]; bloquant: boolean }[]
  avertissements: string[]; pages_declarees: number | null; mots: number; paragraphes: number
}

export interface Livraison {
  id: string; dossier_id?: string; version: number; type_depot: string; nom_original: string; taille_octets: number
  statut_controle: 'conforme' | 'avertissements' | 'non_conforme'; pages_declarees: number | null
  commentaire: string | null; depose_par?: string | null; depose_le: string; rapport_controle?: Rapport
}

export interface Correction {
  id: string; message: string; created_at: string; date_limite: string | null
  livraison_id: string | null; demandee_par?: string | null; resolue_le: string | null
}

export interface AffectationInfo {
  id: string; prestataire_id: string; prestataire_nom: string | null; statut: string; type_role: string
  date_attribution: string; date_limite_rendu: string | null; date_rendu_effectif: string | null; commentaire: string | null
}

export interface DossierDetail extends DossierResume {
  payeur_id: string | null; payeur_nom: string | null; date_reception_audio: string
  niveau_confidentialite: string; notes_internes: string | null
  criteres_tarif: Criteres | null; nombre_pages_final: string | null
  motif_blocage: string | null; statut_avant_blocage: string | null; valide_le: string | null
  echeance_mode: 'calculee' | 'manuelle'
  echeance_figee_le: string | null
  echeance_detail: { regle: string | null; delai_jours?: number; type_jours?: string; date_reception?: string; motif?: string } | null
  transitions_possibles: string[]; audio: Audio | null; affectations: AffectationInfo[]
  livraisons: Livraison[]; corrections: Correction[]; acces_finance: boolean
}

export interface Criteres {
  urgence: boolean; sans_prise_de_note: boolean; prestation_speciale: boolean
  type_prestation_speciale?: string | null; volume_estime_pages?: number | null
}

export interface Suggestion {
  prestataire_id: string; nom: string; score: number; rang: number; disponible: boolean
  charge_actuelle: number; fiabilite_donnees: 'insuffisante' | 'limitee' | 'bonne'
  raisons: string[]; alertes: string[]; indicateurs: Record<string, unknown>
}

export interface Calcul {
  id: string; version_calcul: number; date_calcul: string; nombre_pages: string; statut: string
  montant_client_brut: string; ajustement_client: string; motif_ajustement_client: string | null
  montant_client_final: string; montant_retranscripteur: string; montant_correcteur: string
  montant_prestataires_total: string; marge_brute: string
  regles_appliquees: { regle_libelle: string; cible: string; impact_montant: string; valeur_appliquee: string; grille_version: string }[] | null
  criteres_appliques: { _tarification?: { date_reference: string; majorations_appliquees: string[] } } | null
  grilles_version_snap: Record<string, { nom: string; version: string; type: string; date_debut?: string }> | null
}

export interface Tranche { pages_min: string | number; mode: 'forfait' | 'par_page'; montant: string | number }
export interface ConditionsUrgence { case_cochee: boolean; dossier_signale_urgent: boolean; delai_max_jours: number | null }

export interface VersionTarif {
  id: string; famille_id: string; nom: string; type: string; usage: string; version: string
  statut: 'brouillon' | 'en_vigueur' | 'programmee' | 'archivee' | 'desactivee'
  date_debut: string; date_fin: string | null; active: boolean; brouillon: boolean
  application: 'defaut' | 'instance' | 'attribuee'; type_instance: string | null; description: string | null
  applique_client: boolean; applique_retranscripteur: boolean; conditions: ConditionsUrgence | null
  tranches: Tranche[] | null; majoration: { mode: 'pourcentage' | 'montant'; valeur: string | number } | null
  avancee: boolean; regles: { libelle: string; valeur: string | number; unite: string | null }[]
  utilisee: boolean; creee_par: string | null; date_creation: string
}

export interface FamilleTarif {
  famille_id: string; nom: string; type: string; courante: VersionTarif | null; brouillon: VersionTarif | null
  programmee: VersionTarif | null; versions: VersionTarif[]; attribuee_a: string[]
}

export interface Simulation {
  montant_client: number | string; montant_retranscripteur: number | string; marge: number | string
  grille_client: string | null; grille_retranscripteur: string | null; majorations: string[]
  lignes: { cible: string; libelle: string; montant: number | string }[]; avertissement: string | null
}

export interface RegleDelai {
  id: string; libelle: string; actif: boolean; priorite: number; type_instance: string | null
  duree_min_minutes: number | null; duree_max_minutes: number | null; urgence: boolean | null
  prestation: 'snp' | 'special' | null; delai_jours: number; type_jours: 'calendaires' | 'ouvres'
  description: string | null; modifie_le: string
}

export interface Facture {
  id: string; numero_facture: string; dossier_id: string; dossier_reference: string | null
  payeur_nom: string | null; montant_ht: string; tva_applicable: boolean; taux_tva: string; montant_tva: string
  montant_ttc: string; montant_encaisse: string; reste_a_encaisser: string; date_emission: string
  date_echeance: string | null; statut_paiement: string; annulee_le: string | null; motif_annulation: string | null
  en_retard: boolean
  encaissements: { id: string; montant: string; date_encaissement: string; mode: string | null; reference: string | null }[]
}

export interface Paiement {
  id: string; dossier_id: string; dossier_reference: string | null; prestataire_id: string; prestataire_nom: string | null
  nombre_pages: string; montant_brut: string; ajustement_manuel: string; motif_ajustement: string | null
  montant_final: string; statut: 'a_payer' | 'valide' | 'paye'; date_virement: string | null; reference_virement: string | null
}

export interface Notif {
  id: string; type: string; titre: string; message: string | null; lien: string | null
  dossier_id: string | null; lu: boolean; email_statut: string; created_at: string
}

export interface Mission {
  affectation_id: string; reference: string; titre: string | null; instance: string | null; type_instance: string
  date_seance: string | null; duree_audio_minutes: number | null; echeance: string | null; urgent: boolean
  en_retard: boolean; consignes: string | null; etape: string; etape_label: string; peut_deposer: boolean
  audio: { disponible: boolean; nom_fichier: string | null; taille_octets: number | null } | null
  versions: Livraison[]; corrections: Correction[]; attribue_le: string
}

export interface PrestataireFiche {
  id: string; nom: string; email: string; telephone: string | null; disponible: boolean; actif: boolean
  charge_actuelle: number; grille_tarifaire_id: string | null; specialites: string[]; notes_internes: string | null
  iban_renseigne: boolean; compte: { id: string; email: string; actif: boolean; last_login: string | null } | null
}

export interface ClientFiche {
  id: string; nom: string; type: string; entreprise_mere: string | null; contact_principal: string | null
  email_contact: string | null; telephone: string | null; conditions_paiement: string | null
  grille_tarifaire_id: string | null; actif: boolean
}

export interface Dashboard {
  production: Record<string, number | null>
  finance: Record<string, number> | null
  genere_le: string
}

const d = <T,>(p: Promise<{ data: T }>) => p.then((r) => r.data)

export const api = {
  // Auth
  login: (email: string, password: string) => {
    const body = new URLSearchParams({ username: email, password })
    return d<{ access_token: string; user: Me }>(apiClient.post('/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }))
  },
  me: () => d<Me>(apiClient.get('/auth/me')),
  changePassword: (ancien: string, nouveau: string) =>
    d<{ access_token: string; user: Me }>(apiClient.post('/auth/change-password', { ancien_mot_de_passe: ancien, nouveau_mot_de_passe: nouveau })),
  preferences: (notif_email: boolean) => d<Me>(apiClient.patch('/auth/me/preferences', { notif_email })),
  users: () => d<Me[]>(apiClient.get('/auth/users')),
  createUser: (body: Record<string, unknown>) => d<{ user: Me; mot_de_passe_temporaire: string | null }>(apiClient.post('/auth/users', body)),
  updateUser: (id: string, body: Record<string, unknown>) => d<{ user: Me; mot_de_passe_temporaire: string | null }>(apiClient.patch(`/auth/users/${id}`, body)),
  permissionsCatalogue: () => d<{ permissions: { code: string; libelle: string }[]; par_defaut: Record<string, string[]> }>(apiClient.get('/auth/permissions')),

  dashboard: () => d<Dashboard>(apiClient.get('/dashboard')),

  // Dossiers
  dossiers: (params: Record<string, string | number | boolean | undefined>) =>
    d<{ total: number; items: DossierResume[] }>(apiClient.get('/dossiers', { params })),
  dossier: (id: string) => d<DossierDetail>(apiClient.get(`/dossiers/${id}`)),
  createDossier: (body: Record<string, unknown>) => d<DossierDetail>(apiClient.post('/dossiers', body)),
  updateDossier: (id: string, body: Record<string, unknown>) => d<DossierDetail>(apiClient.patch(`/dossiers/${id}`, body)),
  qualifier: (id: string, body: Record<string, unknown>) => d<DossierDetail>(apiClient.post(`/dossiers/${id}/qualifier`, body)),
  urgence: (id: string, urgent: boolean) => d<DossierDetail>(apiClient.post(`/dossiers/${id}/urgence`, { urgent })),
  bloquer: (id: string, motif: string) => d<DossierDetail>(apiClient.post(`/dossiers/${id}/bloquer`, { motif })),
  debloquer: (id: string) => d<DossierDetail>(apiClient.post(`/dossiers/${id}/debloquer`)),
  archiver: (id: string) => d<DossierDetail>(apiClient.post(`/dossiers/${id}/archiver`)),
  supprimerDossier: (id: string) => apiClient.delete(`/dossiers/${id}`),
  journal: (id: string) => d<{ id: string; timestamp: string; type_action: string; detail: Record<string, unknown> | null; utilisateur_nom: string | null }[]>(apiClient.get(`/dossiers/${id}/journal`, { params: { limit: 200 } })),
  journalGlobal: (params: Record<string, unknown>) => d<{ id: string; timestamp: string; type_action: string; dossier_id: string | null; detail: Record<string, unknown> | null; utilisateur_nom: string | null; ip_source: string | null }[]>(apiClient.get('/journal', { params })),

  // Audios
  audios: (statut: string) => d<Audio[]>(apiClient.get('/audios', { params: { statut } })),
  ajouterLien: (body: Record<string, unknown>) => d<Audio>(apiClient.post('/audios/lien', body)),
  ajouterFichier: (file: File, client_id?: string, duree?: string) => {
    const fd = new FormData()
    fd.append('file', file)
    if (client_id) fd.append('client_id', client_id)
    if (duree) fd.append('duree_minutes', duree)
    return d<Audio>(apiClient.post('/audios/fichier', fd, { headers: { 'Content-Type': 'multipart/form-data' } }))
  },
  modifierAudio: (id: string, body: Record<string, unknown>) => d<Audio>(apiClient.patch(`/audios/${id}`, body)),
  verifierAudio: (id: string) => d<Audio>(apiClient.post(`/audios/${id}/verifier`)),
  associerAudio: (id: string, dossier_id: string) => d<Audio>(apiClient.post(`/audios/${id}/associer`, { dossier_id })),
  ignorerAudio: (id: string) => d<Audio>(apiClient.post(`/audios/${id}/ignorer`)),
  retablirAudio: (id: string) => d<Audio>(apiClient.post(`/audios/${id}/retablir`)),
  synchro: () => d<Record<string, unknown>>(apiClient.get('/audios-synchronisation')),
  lancerSynchro: () => d<Record<string, unknown>>(apiClient.post('/audios-synchronisation')),

  // Attribution
  suggestions: (id: string) => d<{ suggestions: Suggestion[]; avertissement: string }>(apiClient.get(`/dossiers/${id}/suggestions`)),
  attribuer: (id: string, body: Record<string, unknown>) => d(apiClient.post(`/dossiers/${id}/affectations`, body)),
  modifierAffectation: (id: string, body: Record<string, unknown>) => d(apiClient.patch(`/affectations/${id}`, body)),
  retirer: (id: string, motif: string) => d(apiClient.post(`/affectations/${id}/retirer`, { motif })),

  // Livraisons
  commencerRelecture: (id: string) => d(apiClient.post(`/dossiers/${id}/relecture/commencer`)),
  terminerRelecture: (id: string) => d(apiClient.post(`/dossiers/${id}/relecture/terminer`)),
  demanderCorrection: (id: string, body: Record<string, unknown>) => d(apiClient.post(`/dossiers/${id}/corrections`, body)),
  deposerInterne: (id: string, file: File, commentaire: string) => {
    const fd = new FormData()
    fd.append('file', file)
    if (commentaire) fd.append('commentaire', commentaire)
    return d<Livraison>(apiClient.post(`/dossiers/${id}/livraisons`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }))
  },
  valider: (id: string, body: Record<string, unknown>) => d(apiClient.post(`/dossiers/${id}/valider`, body)),
  comparer: (a: string, b: string) => d<{ version_a: number; version_b: number; modifications: number; blocs: { type: string; nombre?: number; avant?: string[]; apres?: string[] }[] }>(apiClient.get(`/livraisons/${a}/comparer/${b}`)),

  // Finance
  calculs: (id: string) => d<Calcul[]>(apiClient.get(`/dossiers/${id}/calculs`)),
  calculer: (id: string, nombre_pages?: string) => d<Calcul>(apiClient.post(`/dossiers/${id}/calculer`, nombre_pages ? { nombre_pages } : {})),
  validerCalcul: (id: string) => d<Calcul>(apiClient.post(`/calculs/${id}/valider`)),
  ajusterCalcul: (id: string, ajustement_client: string, motif_ajustement_client: string) =>
    d<Calcul>(apiClient.post(`/calculs/${id}/ajuster`, { ajustement_client, motif_ajustement_client })),
  factureDossier: (id: string) => d<Facture>(apiClient.get(`/dossiers/${id}/facture`)),
  genererFacture: (id: string, body: Record<string, unknown>) => d<Facture>(apiClient.post(`/dossiers/${id}/generer-facture`, body)),
  factures: (vue: string) => d<{ items: (Facture & DossierResume & { calcul?: { id: string; statut: string; montant_client_final: string } | null; nombre_pages_final?: string })[] }>(apiClient.get('/factures', { params: { vue } })),
  encaisser: (id: string, body: Record<string, unknown>) => d<Facture>(apiClient.post(`/factures/${id}/encaissements`, body)),
  annulerFacture: (id: string, motif: string) => d<Facture>(apiClient.post(`/factures/${id}/annuler`, { motif })),
  paiements: (vue: string) => d<Paiement[]>(apiClient.get('/paiements-prestataires', { params: { vue } })),
  paiementsDossier: (id: string) => d<Paiement[]>(apiClient.get(`/dossiers/${id}/paiements-prestataires`)),
  majPaiement: (id: string, body: Record<string, unknown>) => d<Paiement>(apiClient.patch(`/paiements-prestataires/${id}`, body)),

  // Référentiels
  clients: (actif_only = true) => d<ClientFiche[]>(apiClient.get('/clients', { params: { actif_only } })),
  createClient: (body: Record<string, unknown>) => d<ClientFiche>(apiClient.post('/clients', body)),
  updateClient: (id: string, body: Record<string, unknown>) => d<ClientFiche>(apiClient.patch(`/clients/${id}`, body)),
  prestataires: (actif_only = true) => d<PrestataireFiche[]>(apiClient.get('/prestataires', { params: { actif_only } })),
  createPrestataire: (body: Record<string, unknown>) => d<PrestataireFiche>(apiClient.post('/prestataires', body)),
  updatePrestataire: (id: string, body: Record<string, unknown>) => d<PrestataireFiche>(apiClient.patch(`/prestataires/${id}`, body)),
  compteprestataire: (id: string) => d<{ email: string; mot_de_passe_temporaire: string }>(apiClient.post(`/prestataires/${id}/compte`)),
  performances: () => d<Record<string, unknown>[]>(apiClient.get('/prestataires/performances')),
  iban: (id: string) => d<{ iban: string | null }>(apiClient.get(`/prestataires/${id}/iban`)),

  // Tarifs et paramètres commerciaux
  catalogue: (usage: 'client' | 'retranscripteur' | 'majorations') => d<FamilleTarif[]>(apiClient.get('/tarifs/catalogue', { params: { usage } })),
  creerGrille: (body: Record<string, unknown>) => d<VersionTarif>(apiClient.post('/tarifs/grilles', body)),
  creerMajoration: (body: Record<string, unknown>) => d<VersionTarif>(apiClient.post('/tarifs/majorations', body)),
  modifierBrouillon: (id: string, body: Record<string, unknown>) => d<VersionTarif>(apiClient.put(`/tarifs/grilles/${id}`, body)),
  reviser: (id: string, body: Record<string, unknown>) => d<VersionTarif>(apiClient.post(`/tarifs/grilles/${id}/reviser`, body)),
  publier: (id: string, date_debut: string) => d<VersionTarif>(apiClient.post(`/tarifs/grilles/${id}/publier`, { date_debut })),
  desactiverGrille: (id: string) => d<VersionTarif>(apiClient.post(`/tarifs/grilles/${id}/desactiver`)),
  activerGrille: (id: string) => d<VersionTarif>(apiClient.post(`/tarifs/grilles/${id}/activer`)),
  supprimerBrouillon: (id: string) => apiClient.delete(`/tarifs/grilles/${id}`),
  simuler: (body: Record<string, unknown>) => d<Simulation>(apiClient.post('/tarifs/simuler', body)),

  // Délais et paramètres généraux
  delais: () => d<{ regles: RegleDelai[]; generaux: { cle: string; libelle: string; valeur: number | null }[] }>(apiClient.get('/parametres/delais')),
  creerRegleDelai: (body: Record<string, unknown>) => d<RegleDelai>(apiClient.post('/parametres/delais/regles', body)),
  modifierRegleDelai: (id: string, body: Record<string, unknown>) => d<RegleDelai>(apiClient.put(`/parametres/delais/regles/${id}`, body)),
  supprimerRegleDelai: (id: string) => apiClient.delete(`/parametres/delais/regles/${id}`),
  parametresGeneraux: (valeurs: Record<string, number | null>) => d(apiClient.put('/parametres/generaux', { valeurs })),
  simulerDelai: (body: Record<string, unknown>) => d<{ echeance: string | null; detail: { regle: string; delai_jours: number; type_jours: string } | null; message: string | null }>(apiClient.post('/parametres/delais/simuler', body)),
  recalculerEcheance: (id: string) => d<DossierDetail>(apiClient.post(`/dossiers/${id}/echeance/recalculer`)),

  // Notifications
  notifications: () => d<{ non_lues: number; email_configure: boolean; items: Notif[] }>(apiClient.get('/notifications')),
  lireNotif: (id: string) => d<Notif>(apiClient.post(`/notifications/${id}/lu`)),
  toutLire: () => d(apiClient.post('/notifications/tout-lu')),

  // Espace prestataire
  missions: (terminees = false) => d<Mission[]>(apiClient.get('/espace-prestataire/missions', { params: { terminees } })),
  commencer: (aid: string) => d<Mission>(apiClient.post(`/espace-prestataire/missions/${aid}/commencer`)),
  deposerPV: (aid: string, file: File, commentaire: string) => {
    const fd = new FormData()
    fd.append('file', file)
    if (commentaire) fd.append('commentaire', commentaire)
    return d<Mission>(apiClient.post(`/espace-prestataire/missions/${aid}/livraisons`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }))
  },

  // Espace client
  clientDossiers: () => d<{ reference: string; titre: string | null; type_instance: string; date_seance: string | null; etape: string; created_at: string }[]>(apiClient.get('/espace-client/dossiers')),
  clientDepots: () => d<{ id: string; nom_fichier: string; taille_octets: number; created_at: string; pris_en_charge: boolean }[]>(apiClient.get('/espace-client/audios')),
  clientDeposer: (file: File, commentaire: string) => {
    const fd = new FormData()
    fd.append('file', file)
    if (commentaire) fd.append('commentaire', commentaire)
    return d(apiClient.post('/espace-client/audios', fd, { headers: { 'Content-Type': 'multipart/form-data' } }))
  },
}
