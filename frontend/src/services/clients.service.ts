import { apiClient } from './api'
import type { Client, ClientCreate } from '@/types'

export const clientsService = {
  async list(actif_only = true): Promise<Client[]> {
    const { data } = await apiClient.get<Client[]>('/clients', { params: { actif_only } })
    return data
  },

  async get(id: string): Promise<Client> {
    const { data } = await apiClient.get<Client>(`/clients/${id}`)
    return data
  },

  async create(payload: ClientCreate): Promise<Client> {
    const { data } = await apiClient.post<Client>('/clients', payload)
    return data
  },

  async update(id: string, payload: Partial<ClientCreate> & { actif?: boolean }): Promise<Client> {
    const { data } = await apiClient.patch<Client>(`/clients/${id}`, payload)
    return data
  },
}
