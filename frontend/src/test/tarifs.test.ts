import { describe, expect, it } from 'vitest'
import { libelleConditions, libelleMajoration, libellesTranches } from '@/lib/tarifs'
import type { VersionTarif } from '@/lib/api'

describe('affichage des tarifs', () => {
  it('transforme les seuils en tranches lisibles', () => {
    const l = libellesTranches([
      { pages_min: '0', mode: 'forfait', montant: '50' },
      { pages_min: '10', mode: 'forfait', montant: '100' },
      { pages_min: '21', mode: 'forfait', montant: '150' },
      { pages_min: '100.01', mode: 'par_page', montant: '5' },
    ]).map((x) => x.libelle)
    expect(l).toEqual(['1 à 9 pages', '10 à 20 pages', '21 à 100 pages', 'Plus de 100 pages'])
  })
  it('affiche une tranche unique et les prix par page', () => {
    const [t] = libellesTranches([{ pages_min: '1', mode: 'par_page', montant: '4' }])
    expect(t.libelle).toBe('Toutes les pages')
    expect(t.prix).toMatch(/4,00\s?€ \/ page/)
  })
  it('décrit une majoration et ses conditions', () => {
    const v = { type: 'urgence', majoration: { mode: 'pourcentage', valeur: '30.0000' },
      conditions: { case_cochee: true, dossier_signale_urgent: false, delai_max_jours: 3 } } as unknown as VersionTarif
    expect(libelleMajoration(v)).toBe('+30 %')
    expect(libelleConditions(v)).toBe('Si case « Urgence » cochée ou délai ≤ 3 jour(s) entre réception et échéance')
  })
})
