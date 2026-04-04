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

  async openPdf(factureId: string): Promise<void> {
    const response = await apiClient.get(`/factures/${factureId}/pdf`, { responseType: 'blob' })
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  },
}
