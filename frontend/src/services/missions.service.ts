import { apiClient } from './api'
import type { Mission, FichierDossier } from '@/types'

export const missionsService = {
  list(): Promise<Mission[]> {
    return apiClient.get('/missions/mes-dossiers').then((r) => r.data)
  },

  livrer(affectationId: string): Promise<{ statut: string; date_rendu_effectif: string }> {
    return apiClient.post(`/affectations/${affectationId}/livrer`).then((r) => r.data)
  },

  getFichiers(dossierId: string): Promise<FichierDossier[]> {
    return apiClient.get(`/missions/fichiers/${dossierId}`).then((r) => r.data)
  },
}
