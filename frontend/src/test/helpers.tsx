import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { render } from '@testing-library/react'
import type { Me } from '@/lib/api'
import { AuthContext, type AuthValue } from '@/lib/session'

export function makeUser(over: Partial<Me> = {}): Me {
  return {
    id: 'u1', email: 'u@exemple.fr', nom: 'Camille Martin', role: 'administratrice', actif: true,
    created_at: '2026-01-01T00:00:00Z', last_login: null, must_change_password: false, notif_email: true,
    prestataire_id: null, client_id: null, permissions: [], permissions_personnalisees: null, ...over,
  }
}

export function renderWithAuth(ui: ReactNode, user: Me | null, path = '/', extraRoutes: { path: string; element: ReactNode }[] = []) {
  const value: AuthValue = {
    user, ready: true, login: async () => user as Me, logout: () => undefined, setSession: () => undefined,
    refresh: async () => undefined, can: (p) => !!user?.permissions.includes(p),
    isPrestataire: user?.role === 'retranscripteur', isClient: user?.role === 'client',
  }
  return render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={path} element={ui} />
          {extraRoutes.map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}
