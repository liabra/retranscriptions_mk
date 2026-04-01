import { apiClient } from './api'
import type { TokenResponse, User } from '@/types'

export const authService = {
  async login(email: string, password: string): Promise<TokenResponse> {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    const { data } = await apiClient.post<TokenResponse>('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    return data
  },

  async getMe(): Promise<User> {
    const { data } = await apiClient.get<User>('/auth/me')
    return data
  },

  logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
  },

  saveSession(data: TokenResponse) {
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
  },

  getStoredUser(): User | null {
    const raw = localStorage.getItem('user')
    if (!raw) return null
    try {
      return JSON.parse(raw) as User
    } catch {
      return null
    }
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token')
  },
}
