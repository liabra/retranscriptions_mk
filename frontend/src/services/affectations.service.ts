import { apiClient } from './api'
import type { Affectation, AffectationCreate, AffectationWithDossier } from '@/types'

export const affectationsService = {
  mesAffectations(): Promise<AffectationWithDossier[]> {
    return apiClient.get('/mes-affectations').then((r) => r.data)
  },

  list(dossierId: string): Promise<Affectation[]> {
    return apiClient.get(`/dossiers/${dossierId}/affectations`).then((r) => r.data)
  },

  create(dossierId: string, payload: AffectationCreate): Promise<Affectation> {
    return apiClient.post(`/dossiers/${dossierId}/affectations`, payload).then((r) => r.data)
  },

  update(affectationId: string, payload: Partial<Pick<Affectation, 'statut' | 'date_limite_rendu' | 'date_rendu_effectif' | 'commentaire'>>): Promise<Affectation> {
    return apiClient.patch(`/affectations/${affectationId}`, payload).then((r) => r.data)
  },
}
