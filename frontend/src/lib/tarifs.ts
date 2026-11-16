import type { Tranche, VersionTarif } from '@/lib/api'
import { fDate, fMoney } from '@/lib/format'

export interface TrancheEdit { pages_min: string; mode: 'forfait' | 'par_page'; montant: string }

const num = (v: string | number) => Number(String(v).replace(',', '.'))

/** Libellés lisibles des tranches : « 10 à 20 pages », « Plus de 100 pages »… */
export function libellesTranches(tranches: (Tranche | TrancheEdit)[]): { tranche: Tranche | TrancheEdit; libelle: string; prix: string }[] {
  const tri = [...tranches].filter((t) => String(t.pages_min) !== '').sort((a, b) => num(a.pages_min) - num(b.pages_min))
  return tri.map((t, i) => {
    const debut = num(t.pages_min)
    const suivant = tri[i + 1] ? num(tri[i + 1].pages_min) : null
    const de = Number.isInteger(debut) ? Math.max(debut, 1) : null
    let libelle: string
    if (de === null) libelle = `Plus de ${Math.floor(debut)} pages`
    else if (suivant === null) libelle = de <= 1 ? 'Toutes les pages' : `${de} pages et plus`
    else {
      const fin = Number.isInteger(suivant) ? suivant - 1 : Math.floor(suivant)
      libelle = fin <= de ? `${de} page${de > 1 ? 's' : ''}` : `${de} à ${fin} pages`
    }
    const prix = t.mode === 'par_page' ? `${fMoney(num(t.montant))} / page` : fMoney(num(t.montant))
    return { tranche: t, libelle, prix }
  })
}

export const STATUT_TARIF: Record<string, { label: string; tone: string }> = {
  en_vigueur: { label: 'En vigueur', tone: 'green' },
  programmee: { label: 'Programmée', tone: 'blue' },
  brouillon: { label: 'Brouillon', tone: 'amber' },
  archivee: { label: 'Archivée', tone: 'gray' },
  desactivee: { label: 'Désactivée', tone: 'red' },
}

export function periode(v: VersionTarif): string {
  if (v.brouillon) return 'Non publiée'
  if (v.statut === 'desactivee') return v.date_fin ? `Désactivée (prévue du ${fDate(v.date_debut)} au ${fDate(v.date_fin)})` : 'Désactivée'
  if (v.date_fin) return `Du ${fDate(v.date_debut)} au ${fDate(v.date_fin)}`
  return `${v.statut === 'programmee' ? 'À partir du' : 'Depuis le'} ${fDate(v.date_debut)}`
}

export function libelleMajoration(v: VersionTarif): string {
  if (!v.majoration) return 'Configuration avancée'
  const val = num(v.majoration.valeur)
  return v.majoration.mode === 'pourcentage' ? `+${val.toLocaleString('fr-FR')} %` : `+${fMoney(val)}`
}

export function libelleConditions(v: VersionTarif): string {
  if (v.type === 'snp') return 'Dossiers « sans prise de notes »'
  if (v.type === 'special') return 'Dossiers avec prestation particulière'
  const c = v.conditions
  if (!c) return '—'
  const parts = []
  if (c.case_cochee) parts.push('case « Urgence » cochée')
  if (c.dossier_signale_urgent) parts.push('dossier signalé urgent')
  if (c.delai_max_jours !== null && c.delai_max_jours !== undefined) parts.push(`délai ≤ ${c.delai_max_jours} jour(s) entre réception et échéance`)
  return parts.length ? `Si ${parts.join(' ou ')}` : 'Jamais déclenchée (aucune condition)'
}

export const aujourdhui = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
