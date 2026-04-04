// Grille tarifaire A2C — forfaits par tranche de pages
// Source : modalités de retranscription A2C

export interface TrancheForfait {
  label: string
  min: number
  max: number
  montant: number
}

export const TRANCHES_CLIENT: TrancheForfait[] = [
  { label: '1 – 9 pages', min: 1, max: 9, montant: 50 },
  { label: '10 – 20 pages', min: 10, max: 20, montant: 100 },
  { label: '21 – 30 pages', min: 21, max: 30, montant: 150 },
  { label: '31 – 40 pages', min: 31, max: 40, montant: 200 },
  { label: '41 – 50 pages', min: 41, max: 50, montant: 250 },
  { label: '51 – 60 pages', min: 51, max: 60, montant: 300 },
  { label: '61 – 70 pages', min: 61, max: 70, montant: 350 },
  { label: '71 – 80 pages', min: 71, max: 80, montant: 400 },
  { label: '81 – 90 pages', min: 81, max: 90, montant: 450 },
  { label: '91 – 100 pages', min: 91, max: 100, montant: 500 },
]

/** Retourne le montant forfaitaire pour un nombre de pages donné, ou null si hors grille. */
export function getForfaitClient(pages: number): number | null {
  const t = TRANCHES_CLIENT.find((t) => pages >= t.min && pages <= t.max)
  return t ? t.montant : null
}

/** Retourne la tranche correspondante, ou null. */
export function getTranche(pages: number): TrancheForfait | null {
  return TRANCHES_CLIENT.find((t) => pages >= t.min && pages <= t.max) ?? null
}

/**
 * Délai de livraison recommandé selon la durée audio.
 * - ≤ 1h : 7 jours
 * - 2h – 4h : 18 jours
 * - > 4h : 25 jours
 */
export function getDelaiLivraison(dureeMinutes: number): string {
  const h = dureeMinutes / 60
  if (h <= 1) return '7 jours'
  if (h <= 4) return '18 jours'
  return '25 jours'
}
