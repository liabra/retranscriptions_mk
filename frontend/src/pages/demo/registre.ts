import type { Parcours } from './moteur'
import { PARCOURS_PV } from './pv'
import { PARCOURS_CAS, PARCOURS_DELAIS, PARCOURS_EQUIPE, PARCOURS_MISSION, PARCOURS_TARIFS } from './autres'

export const PARCOURS: Parcours[] = [PARCOURS_PV, PARCOURS_TARIFS, PARCOURS_DELAIS, PARCOURS_CAS, PARCOURS_EQUIPE, PARCOURS_MISSION]

export const parcoursPour = (prestataire: boolean) => PARCOURS.filter((p) => (p.audience === 'prestataire') === prestataire)
