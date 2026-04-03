import { apiClient } from './api'
import type { CalculTarifaire } from '@/types'

export const calculsService = {
  calculer(dossierId: string, nombre_pages: string, force_recalcul = false): Promise<CalculTarifaire> {
    return apiClient
      .post(`/dossiers/${dossierId}/calculer`, { nombre_pages, force_recalcul })
      .then((r) => r.data)
  },

  get(calculId: string): Promise<CalculTarifaire> {
    return apiClient.get(`/calculs/${calculId}`).then((r) => r.data)
  },

  list(dossierId: string): Promise<CalculTarifaire[]> {
    return apiClient.get(`/dossiers/${dossierId}/calculs`).then((r) => r.data)
  },

  valider(calculId: string): Promise<CalculTarifaire> {
    return apiClient.post(`/calculs/${calculId}/valider`).then((r) => r.data)
  },

  ajuster(
    calculId: string,
    ajustement_client: string,
    motif_ajustement_client: string,
  ): Promise<CalculTarifaire> {
    return apiClient
      .post(`/calculs/${calculId}/ajuster`, { ajustement_client, motif_ajustement_client })
      .then((r) => r.data)
  },
}
