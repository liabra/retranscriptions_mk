import { apiClient } from './api'
import type { User, UserUpdate } from '@/types'

export const usersService = {
  async list(): Promise<User[]> {
    const { data } = await apiClient.get<User[]>('/auth/users')
    return data
  },

  async create(payload: { email: string; nom: string; password: string; role: string }): Promise<User> {
    const { data } = await apiClient.post<User>('/auth/register', payload)
    return data
  },

  async update(id: string, payload: UserUpdate): Promise<User> {
    const { data } = await apiClient.patch<User>(`/auth/users/${id}`, payload)
    return data
  },
}
