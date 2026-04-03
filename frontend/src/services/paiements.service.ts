import { apiClient } from './api'
import type { PaiementPrestataire } from '@/types'

export const paiementsService = {
  generer(dossierId: string): Promise<PaiementPrestataire[]> {
    return apiClient
      .post(`/dossiers/${dossierId}/generer-paiements-prestataires`)
      .then((r) => r.data)
  },

  list(dossierId: string): Promise<PaiementPrestataire[]> {
    return apiClient.get(`/dossiers/${dossierId}/paiements-prestataires`).then((r) => r.data)
  },

  update(
    paiementId: string,
    payload: {
      statut?: string
      date_virement?: string
      reference_virement?: string
      ajustement_manuel?: string
      motif_ajustement?: string
    },
  ): Promise<PaiementPrestataire> {
    return apiClient.patch(`/paiements-prestataires/${paiementId}`, payload).then((r) => r.data)
  },
}
