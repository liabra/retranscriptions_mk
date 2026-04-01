import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import type { User } from '@/types'
import { authService } from '@/services/auth.service'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(authService.getStoredUser())
  const [isLoading, setIsLoading] = useState(false)

  // Revalidate token on mount
  useEffect(() => {
    if (!authService.isAuthenticated()) return
    authService.getMe()
      .then(setUser)
      .catch(() => {
        authService.logout()
        setUser(null)
      })
  }, [])

  async function login(email: string, password: string) {
    setIsLoading(true)
    try {
      const data = await authService.login(email, password)
      authService.saveSession(data)
      setUser(data.user)
    } finally {
      setIsLoading(false)
    }
  }

  function logout() {
    authService.logout()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
