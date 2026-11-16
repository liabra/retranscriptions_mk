import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, type Me } from '@/lib/api'
import { AuthContext } from '@/lib/session'
import { tokenStore } from '@/services/api'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [ready, setReady] = useState(() => !tokenStore.get())

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) { setUser(null); return }
    try { setUser(await api.me()) } catch { tokenStore.clear(); setUser(null) }
  }, [])

  useEffect(() => {
    if (!tokenStore.get()) return
    api.me().then(setUser).catch(() => tokenStore.clear()).finally(() => setReady(true))
  }, [])

  const setSession = (token: string, u: Me) => { tokenStore.set(token); setUser(u) }

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password)
    setSession(res.access_token, res.user)
    return res.user
  }

  const logout = () => { tokenStore.clear(); setUser(null) }

  // Affichage seulement : chaque droit est revérifié par l'API
  const can = (perm: string) => !!user?.permissions.includes(perm)
  const isPrestataire = user?.role === 'retranscripteur' || user?.role === 'correcteur'
  const isClient = user?.role === 'client'

  return (
    <AuthContext.Provider value={{ user, ready, login, logout, setSession, refresh, can, isPrestataire, isClient }}>
      {children}
    </AuthContext.Provider>
  )
}
