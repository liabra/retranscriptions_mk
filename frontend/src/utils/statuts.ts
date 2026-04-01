import type { StatutDossier, RoleEnum } from '@/types'

export const STATUT_LABELS: Record<StatutDossier, string> = {
  recu: 'Reçu',
  en_qualification: 'En qualification',
  estime: 'Estimé',
  a_attribuer: 'À attribuer',
  en_retranscription: 'En retranscription',
  a_corriger: 'À corriger',
  en_correction: 'En correction',
  en_mise_en_forme: 'En mise en forme',
  calcul_en_cours: 'Calcul en cours',
  a_valider: 'À valider',
  envoye: 'Envoyé',
  facture: 'Facturé',
  paye_entrant: 'Payé (entrant)',
  prestataires_payes: 'Prestataires payés',
  archive: 'Archivé',
  bloque: 'Bloqué',
  incomplet: 'Incomplet',
}

export const STATUT_COLOR: Record<StatutDossier, string> = {
  recu: 'badge-gray',
  en_qualification: 'badge-blue',
  estime: 'badge-blue',
  a_attribuer: 'badge-yellow',
  en_retranscription: 'badge-yellow',
  a_corriger: 'badge-yellow',
  en_correction: 'badge-yellow',
  en_mise_en_forme: 'badge-yellow',
  calcul_en_cours: 'badge-yellow',
  a_valider: 'badge-orange',
  envoye: 'badge-green',
  facture: 'badge-green',
  paye_entrant: 'badge-green',
  prestataires_payes: 'badge-green',
  archive: 'badge-gray',
  bloque: 'badge-red',
  incomplet: 'badge-red',
}

export const ROLE_LABELS: Record<RoleEnum, string> = {
  administratrice: 'Administratrice',
  coordinatrice: 'Coordinatrice',
  retranscripteur: 'Retranscripteur',
  correcteur: 'Correcteur',
  comptabilite: 'Comptabilité',
  lecture_seule: 'Lecture seule',
}

export function isRetard(dateLimite: string | null): boolean {
  if (!dateLimite) return false
  return new Date(dateLimite) < new Date()
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Intl.DateTimeFormat('fr-FR').format(new Date(dateStr))
}

export function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(dateStr))
}
