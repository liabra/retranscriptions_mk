import { apiClient } from './api'
import type { Prestataire, PrestaCreate } from '@/types'

export const prestatairesService = {
  async list(params?: { actif_only?: boolean; disponible_only?: boolean }): Promise<Prestataire[]> {
    const { data } = await apiClient.get<Prestataire[]>('/prestataires', { params })
    return data
  },

  async get(id: string): Promise<Prestataire> {
    const { data } = await apiClient.get<Prestataire>(`/prestataires/${id}`)
    return data
  },

  async create(payload: PrestaCreate): Promise<Prestataire> {
    const { data } = await apiClient.post<Prestataire>('/prestataires', payload)
    return data
  },

  async update(id: string, payload: Partial<PrestaCreate> & { actif?: boolean; disponible?: boolean }): Promise<Prestataire> {
    const { data } = await apiClient.patch<Prestataire>(`/prestataires/${id}`, payload)
    return data
  },
}
