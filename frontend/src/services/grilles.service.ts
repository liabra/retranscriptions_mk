import { apiClient } from './api'
import type { GrilleTarifaire, GrilleCreate, GrilleUpdate, RegleTarifaire, RegleCreate } from '@/types'

export const grillesService = {
  list(actifOnly = false): Promise<GrilleTarifaire[]> {
    return apiClient.get('/grilles', { params: { actif_only: actifOnly } }).then((r) => r.data)
  },

  get(id: string): Promise<GrilleTarifaire & { regles: RegleTarifaire[] }> {
    return apiClient.get(`/grilles/${id}`).then((r) => r.data)
  },

  create(payload: GrilleCreate): Promise<GrilleTarifaire> {
    return apiClient.post('/grilles', payload).then((r) => r.data)
  },

  update(id: string, payload: GrilleUpdate): Promise<GrilleTarifaire> {
    return apiClient.patch(`/grilles/${id}`, payload).then((r) => r.data)
  },

  deactivate(id: string): Promise<void> {
    return apiClient.delete(`/grilles/${id}`).then(() => undefined)
  },

  createRegle(grilleId: string, payload: RegleCreate): Promise<RegleTarifaire> {
    return apiClient.post(`/grilles/${grilleId}/regles`, payload).then((r) => r.data)
  },

  updateRegle(regleId: string, payload: Partial<RegleCreate>): Promise<RegleTarifaire> {
    return apiClient.patch(`/regles/${regleId}`, payload).then((r) => r.data)
  },

  deleteRegle(regleId: string): Promise<void> {
    return apiClient.delete(`/regles/${regleId}`).then(() => undefined)
  },
}
