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

// ─── API ─────────────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string | { msg: string; type: string }[]
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
}
