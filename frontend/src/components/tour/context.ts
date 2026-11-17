import { createContext, useContext } from 'react'
import type { TourStep } from './tours'

export interface TourValue {
  start: (tourId: string) => void
  stop: () => void
  actif: string | null
}

export const TourContext = createContext<TourValue>({ start: () => undefined, stop: () => undefined, actif: null })

export const useTour = () => useContext(TourContext)

/** Étapes visibles pour un utilisateur (selon ses droits). */
export function etapesVisibles(steps: TourStep[], can: (perm: string) => boolean): TourStep[] {
  return steps.filter((s) => !s.perms || s.perms.some(can))
}

const CLE = 'a2c_guide_vu_'
export const guideVu = (userId: string): boolean => {
  try { return localStorage.getItem(CLE + userId) === '1' } catch { return true }
}
export const marquerGuideVu = (userId: string): void => {
  try { localStorage.setItem(CLE + userId, '1') } catch { /* stockage indisponible */ }
}
