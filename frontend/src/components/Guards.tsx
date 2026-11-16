import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { PageLoader } from '@/components/ui'
import { homeFor, useAuth } from '@/lib/session'

export type Rule = 'interne' | 'prestataire' | 'client' | 'tous'

/** Garde d'affichage : le contrôle réel des droits est fait par l'API sur chaque requête. */
export function Guard({ rule, perm, children }: { rule: Rule; perm?: string[]; children: ReactNode }) {
  const { user, ready, can, isPrestataire, isClient } = useAuth()
  if (!ready) return <PageLoader />
  if (!user) return <Navigate to="/login" replace />
  if (user.must_change_password) return <Navigate to="/mot-de-passe" replace />
  const interne = !isPrestataire && !isClient
  const ok = rule === 'tous' || (rule === 'interne' && interne) || (rule === 'prestataire' && isPrestataire) || (rule === 'client' && isClient)
  if (!ok || (perm && !perm.some(can))) return <Navigate to={homeFor(user)} replace />
  return <>{children}</>
}

export function Session({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth()
  if (!ready) return <PageLoader />
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export function Accueil() {
  const { user, ready } = useAuth()
  if (!ready) return <PageLoader />
  return <Navigate to={homeFor(user)} replace />
}

