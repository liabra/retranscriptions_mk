import { createContext, useContext } from 'react'
import type { Me } from '@/lib/api'

export interface AuthValue {
  user: Me | null
  ready: boolean
  login: (email: string, password: string) => Promise<Me>
  logout: () => void
  setSession: (token: string, user: Me) => void
  refresh: () => Promise<void>
  can: (perm: string) => boolean
  isPrestataire: boolean
  isClient: boolean
}

export const AuthContext = createContext<AuthValue | null>(null)

export function useAuth(): AuthValue {
  const v = useContext(AuthContext)
  if (!v) throw new Error('useAuth doit être utilisé dans AuthProvider')
  return v
}

export function homeFor(user: Me | null): string {
  if (!user) return '/login'
  if (user.must_change_password) return '/mot-de-passe'
  if (user.role === 'retranscripteur' || user.role === 'correcteur') return '/mes-missions'
  if (user.role === 'client') return '/mon-espace'
  return '/tableau-de-bord'
}
