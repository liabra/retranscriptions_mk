import { apiClient } from './api'
import type { Dossier, DossierListItem, DossierCreate, StatutDossier } from '@/types'

export const dossiersService = {
  async list(params?: {
    statut?: StatutDossier
    urgent_only?: boolean
    client_id?: string
    limit?: number
    offset?: number
  }): Promise<DossierListItem[]> {
    const { data } = await apiClient.get<DossierListItem[]>('/dossiers', { params })
    return data
  },

  async get(id: string): Promise<Dossier> {
    const { data } = await apiClient.get<Dossier>(`/dossiers/${id}`)
    return data
  },

  async create(payload: DossierCreate): Promise<Dossier> {
    const { data } = await apiClient.post<Dossier>('/dossiers', payload)
    return data
  },

  async forceUrgent(id: string): Promise<Dossier> {
    const { data } = await apiClient.post<Dossier>(`/dossiers/${id}/force-urgent`)
    return data
  },

  async transition(id: string, statut: StatutDossier): Promise<Dossier> {
    const { data } = await apiClient.post<Dossier>(`/dossiers/${id}/transition`, { statut })
    return data
  },
}
