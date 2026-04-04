// ─── Auth ────────────────────────────────────────────────────────────────────

export type RoleEnum =
  | 'administratrice'
  | 'coordinatrice'
  | 'retranscripteur'
  | 'correcteur'
  | 'comptabilite'
  | 'lecture_seule'

export interface User {
  id: string
  email: string
  nom: string
  role: RoleEnum
  actif: boolean
  created_at: string
  last_login: string | null
}

export interface UserUpdate {
  nom?: string
  role?: RoleEnum
  actif?: boolean
  password?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

// ─── Dossier ─────────────────────────────────────────────────────────────────

export type StatutDossier =
  | 'recu'
  | 'en_qualification'
  | 'estime'
  | 'a_attribuer'
  | 'en_retranscription'
  | 'a_corriger'
  | 'en_correction'
  | 'en_mise_en_forme'
  | 'calcul_en_cours'
  | 'a_valider'
  | 'envoye'
  | 'facture'
  | 'paye_entrant'
  | 'prestataires_payes'
  | 'archive'
  | 'bloque'
  | 'incomplet'

export type TypeInstance = 'CE' | 'CMAS' | 'CSSCT' | 'Autre'
export type NiveauConfidentialite = 'standard' | 'renforce' | 'absolu'

export interface DossierListItem {
  id: string
  reference: string
  titre: string | null
  statut: StatutDossier
  type_instance: TypeInstance
  date_limite: string | null
  est_urgent: boolean
  client_id: string
  created_at: string
}

export interface Dossier extends DossierListItem {
  date_seance: string | null
  date_reception_audio: string
  date_envoi_client: string | null
  payeur_id: string | null
  duree_audio_minutes: number | null
  nombre_pages_final: string | null
  criteres_tarif: Record<string, unknown> | null
  calcul_tarifaire_id: string | null
  niveau_confidentialite: NiveauConfidentialite
  notes_internes: string | null
  updated_at: string
}

export interface DossierCreate {
  type_instance: TypeInstance
  client_id: string
  payeur_id?: string
  date_seance?: string
  date_reception_audio: string
  date_limite?: string
  duree_audio_minutes?: number
  niveau_confidentialite?: NiveauConfidentialite
  notes_internes?: string
  titre?: string
}

// ─── Client ──────────────────────────────────────────────────────────────────

export type TypeClient = 'CE' | 'CMAS' | 'CSSCT' | 'Syndicat' | 'Autre'

export interface Client {
  id: string
  nom: string
  type: TypeClient
  entreprise_mere: string | null
  contact_principal: string | null
  email_contact: string | null
  telephone: string | null
  conditions_paiement: string | null
  grille_tarifaire_id: string | null
  actif: boolean
}

export interface ClientCreate {
  nom: string
  type: TypeClient
  entreprise_mere?: string
  contact_principal?: string
  email_contact?: string
  telephone?: string
  adresse?: string
  conditions_paiement?: string
}

// ─── Prestataire ─────────────────────────────────────────────────────────────

export type RolePresta = 'retranscripteur' | 'correcteur' | 'les_deux'

export interface Prestataire {
  id: string
  nom: string
  role: RolePresta
  email: string
  telephone: string | null
  disponible: boolean
  charge_actuelle: number
  note_qualite: string
  grille_tarifaire_id: string | null
  actif: boolean
}

export interface PrestaCreate {
  nom: string
  role: RolePresta
  email: string
  telephone?: string
  disponible?: boolean
  iban?: string
}

// ─── Affectation ─────────────────────────────────────────────────────────────

export type RoleAffectation = 'retranscripteur' | 'correcteur'
export type StatutAffectation = 'en_attente' | 'en_cours' | 'livre' | 'valide' | 'rejete'

export interface Affectation {
  id: string
  dossier_id: string
  prestataire_id: string
  type_role: RoleAffectation
  statut: StatutAffectation
  date_attribution: string
  date_limite_rendu: string | null
  date_rendu_effectif: string | null
  montant_calcule: string | null
  commentaire: string | null
  grille_snap: Record<string, unknown> | null
}

export interface AffectationCreate {
  prestataire_id: string
  type_role: RoleAffectation
  date_limite_rendu?: string
  commentaire?: string
}

// ─── Fichier ─────────────────────────────────────────────────────────────────

export type TypeDocument =
  | 'audio_brut'
  | 'retranscription_v1'
  | 'retranscription_corrigee'
  | 'document_paiement'
  | 'document_client'
  | 'facture'
  | 'autre'

export type StatutFichier = 'disponible' | 'archive' | 'obsolete'

export interface FichierDossier {
  id: string
  dossier_id: string
  uploaded_by_id: string | null
  type_document: TypeDocument
  nom_fichier: string
  url_onedrive: string
  version: string
  statut: StatutFichier
  commentaire: string | null
  created_at: string
}

export interface FichierCreate {
  type_document: TypeDocument
  nom_fichier: string
  url_onedrive: string
  version?: string
  commentaire?: string
}

// ─── Grilles tarifaires ───────────────────────────────────────────────────────

export type TypeGrille = 'client' | 'retranscripteur' | 'correcteur' | 'urgence' | 'snp' | 'special' | 'prise_de_note'
export type CibleGrille = 'global' | 'client_specifique' | 'prestataire_specifique'
export type TypeRegle = 'base' | 'majoration' | 'remise' | 'forfait' | 'plancher' | 'plafond'
export type ConditionType = 'toujours' | 'si_type_instance' | 'si_urgence' | 'si_snp' | 'si_special' | 'si_duree' | 'si_volume' | 'si_client' | 'combinee'
export type ModeCalcul = 'par_page' | 'forfait_fixe' | 'pourcentage_base' | 'pourcentage_total' | 'multiplicateur'

export interface GrilleTarifaire {
  id: string
  nom: string
  type: TypeGrille
  cible: CibleGrille
  cible_id: string | null
  version: string
  date_debut: string
  date_fin: string | null
  active: boolean
  description: string | null
  creee_par_id: string | null
  date_creation: string
  regles?: RegleTarifaire[]
}

export interface GrilleCreate {
  nom: string
  type: TypeGrille
  cible?: CibleGrille
  cible_id?: string
  version?: string
  date_debut: string
  date_fin?: string
  description?: string
}

export interface GrilleUpdate {
  nom?: string
  version?: string
  date_debut?: string
  date_fin?: string
  active?: boolean
  description?: string
}

export interface RegleTarifaire {
  id: string
  grille_id: string
  libelle: string
  type_regle: TypeRegle
  condition_type: ConditionType
  condition_valeur: Record<string, unknown> | null
  mode_calcul: ModeCalcul
  valeur: string
  unite: string | null
  priorite: number
  cumulable: boolean
  plafond_montant: string | null
  actif: boolean
}

export interface RegleCreate {
  libelle: string
  type_regle: TypeRegle
  condition_type?: ConditionType
  condition_valeur?: Record<string, unknown>
  mode_calcul: ModeCalcul
  valeur: string
  unite?: string
  priorite?: number
  cumulable?: boolean
  plafond_montant?: string
  actif?: boolean
}

// ─── Calcul tarifaire ─────────────────────────────────────────────────────────

export type StatutCalcul = 'estimatif' | 'definitif' | 'ajuste'

export interface LigneCalcul {
  regle_id: string
  regle_libelle: string
  grille_id: string
  grille_version: string
  condition_evaluee: Record<string, unknown>
  valeur_appliquee: string
  impact_montant: string
  cible: string
  ordre_application: number
}

export interface CalculTarifaire {
  id: string
  dossier_id: string
  version_calcul: number
  date_calcul: string
  nombre_pages: string
  criteres_appliques: Record<string, unknown> | null
  regles_appliquees: LigneCalcul[] | null
  montant_client_brut: string
  ajustement_client: string
  motif_ajustement_client: string | null
  montant_client_final: string
  montant_retranscripteur: string
  montant_correcteur: string
  montant_prestataires_total: string
  marge_brute: string
  grilles_version_snap: Record<string, { nom: string; version: string; type: string }> | null
  statut: StatutCalcul
  valide_par_id: string | null
  declenche_par_id: string | null
}

// ─── Facture client ───────────────────────────────────────────────────────────

export type StatutPaiementFacture = 'non_payee' | 'partiellement' | 'soldee'

export interface FactureClient {
  id: string
  numero_facture: string
  dossier_id: string
  payeur_id: string
  calcul_tarifaire_id: string
  montant_ht: string
  tva_applicable: boolean
  taux_tva: string
  montant_tva: string
  montant_ttc: string
  date_emission: string
  date_echeance: string | null
  statut_paiement: StatutPaiementFacture
}

// ─── Paiements prestataires ───────────────────────────────────────────────────

export type StatutPaiementPresta = 'a_payer' | 'valide' | 'paye'

export interface PaiementPrestataire {
  id: string
  affectation_id: string
  dossier_id: string
  prestataire_id: string
  role_paye: string
  nombre_pages: string
  detail_calcul: Record<string, unknown> | null
  montant_brut: string
  ajustement_manuel: string
  motif_ajustement: string | null
  montant_final: string
  statut: StatutPaiementPresta
  date_virement: string | null
  reference_virement: string | null
}

// ─── Journal ──────────────────────────────────────────────────────────────────

export interface JournalEntry {
  id: string
  timestamp: string
  dossier_id: string | null
  utilisateur_id: string | null
  type_action: string
  detail: Record<string, unknown> | null
  ip_source: string | null
}

// ─── Mission (vue prestataire) ────────────────────────────────────────────────

export interface Mission {
  id: string
  reference: string
  titre: string | null
  statut: StatutDossier
  type_instance: TypeInstance
  date_limite: string | null
  est_urgent: boolean
  affectation_id: string | null
  role: RoleAffectation | null
  statut_affectation: StatutAffectation | null
  date_limite_rendu: string | null
}

// ─── API ─────────────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string | { msg: string; type: string }[]
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
}
