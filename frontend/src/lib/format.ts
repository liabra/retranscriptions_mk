export const PRODUCTION: Record<string, { label: string; tone: string }> = {
  a_qualifier: { label: 'À qualifier', tone: 'gray' },
  a_attribuer: { label: 'À attribuer', tone: 'amber' },
  attribue: { label: 'Attribué', tone: 'blue' },
  en_cours: { label: 'En cours', tone: 'blue' },
  livre: { label: 'PV reçu', tone: 'violet' },
  a_relire: { label: 'À relire', tone: 'violet' },
  correction_demandee: { label: 'Correction demandée', tone: 'amber' },
  a_controler: { label: 'À contrôler', tone: 'violet' },
  valide: { label: 'Validé', tone: 'green' },
  archive: { label: 'Archivé', tone: 'gray' },
  bloque: { label: 'Bloqué', tone: 'red' },
}

export const FACTURATION: Record<string, { label: string; tone: string }> = {
  non_applicable: { label: 'Non facturable', tone: 'gray' },
  a_etablir: { label: 'Facture à établir', tone: 'amber' },
  emise: { label: 'Facture émise', tone: 'blue' },
  partiellement_reglee: { label: 'Partiellement réglée', tone: 'violet' },
  reglee: { label: 'Réglée', tone: 'green' },
}

export const PAIEMENT: Record<string, { label: string; tone: string }> = {
  a_payer: { label: 'À payer', tone: 'amber' },
  valide: { label: 'Validé', tone: 'blue' },
  paye: { label: 'Payé', tone: 'green' },
}

export const CONTROLE: Record<string, { label: string; tone: string }> = {
  conforme: { label: 'Conforme', tone: 'green' },
  avertissements: { label: 'Conforme · à vérifier', tone: 'amber' },
  non_conforme: { label: 'Non conforme', tone: 'red' },
}

export const ROLES: Record<string, string> = {
  administratrice: 'Administratrice',
  coordinatrice: 'Coordinatrice · relectrice',
  retranscripteur: 'Retranscripteur·rice',
  correcteur: 'Correcteur (ancien rôle)',
  comptabilite: 'Comptabilité',
  lecture_seule: 'Lecture seule',
  client: 'Client',
}

export const INSTANCES = ['CE', 'CMAS', 'CSSCT', 'Autre']

/** Étapes affichées dans la frise de production. */
export const ETAPES = [
  { key: 'a_qualifier', label: 'Qualification' },
  { key: 'a_attribuer', label: 'Attribution' },
  { key: 'en_cours', label: 'Retranscription' },
  { key: 'livre', label: 'PV reçu' },
  { key: 'a_relire', label: 'Relecture' },
  { key: 'a_controler', label: 'Contrôle' },
  { key: 'valide', label: 'Validé' },
]
const ORDRE: Record<string, number> = {
  a_qualifier: 0, a_attribuer: 1, attribue: 2, en_cours: 2, livre: 3, a_relire: 4,
  correction_demandee: 2, a_controler: 5, valide: 6, archive: 7,
}
export const etapeIndex = (statut: string) => ORDRE[statut] ?? 0

const dateFr = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
const dateTimeFr = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const euro = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })

export function fDate(v?: string | null): string {
  if (!v) return '—'
  const dt = new Date(v)
  return Number.isNaN(dt.getTime()) ? '—' : dateFr.format(dt)
}
export function fDateTime(v?: string | null): string {
  if (!v) return '—'
  const dt = new Date(v)
  return Number.isNaN(dt.getTime()) ? '—' : dateTimeFr.format(dt)
}
export function fMoney(v?: string | number | null): string {
  if (v === null || v === undefined || v === '') return '—'
  return euro.format(Number(v))
}
export function fSize(bytes?: number | null): string {
  if (!bytes) return '—'
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`
  return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} Mo`
}
export function fDuree(min?: number | null): string {
  if (!min) return '—'
  const h = Math.floor(min / 60)
  const m = min % 60
  return h ? `${h} h ${m.toString().padStart(2, '0')}` : `${m} min`
}

/** Échéance relative lisible. */
export function relative(v?: string | null): { texte: string; tone: string } {
  if (!v) return { texte: 'Sans échéance', tone: 'gray' }
  const ms = new Date(v).getTime() - Date.now()
  const jours = Math.round(ms / 86400000)
  if (ms < 0) return { texte: jours === 0 ? 'En retard' : `En retard de ${Math.abs(jours)} j`, tone: 'red' }
  if (ms < 86400000) return { texte: "Aujourd'hui", tone: 'red' }
  if (jours <= 1) return { texte: 'Demain', tone: 'amber' }
  if (jours <= 3) return { texte: `Dans ${jours} jours`, tone: 'amber' }
  return { texte: `Dans ${jours} jours`, tone: 'green' }
}

export const initials = (nom?: string) =>
  (nom ?? '?').split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join('')
