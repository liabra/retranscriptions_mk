import { apiClient } from './api'
import type { FactureClient } from '@/types'

export const facturesService = {
  generer(
    dossierId: string,
    payload: { tva_applicable?: boolean; taux_tva?: string; date_echeance?: string },
  ): Promise<FactureClient> {
    return apiClient.post(`/dossiers/${dossierId}/generer-facture`, payload).then((r) => r.data)
  },

  getByDossier(dossierId: string): Promise<FactureClient> {
    return apiClient.get(`/dossiers/${dossierId}/facture`).then((r) => r.data)
  },

  get(factureId: string): Promise<FactureClient> {
    return apiClient.get(`/factures/${factureId}`).then((r) => r.data)
  },

  updatePaiement(factureId: string, statut_paiement: string): Promise<FactureClient> {
    return apiClient
      .patch(`/factures/${factureId}/paiement`, { statut_paiement })
      .then((r) => r.data)
  },
}
