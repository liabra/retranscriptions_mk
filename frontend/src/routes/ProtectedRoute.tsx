import { Navigate } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthContext'
import type { RoleEnum } from '@/types'
import { PageLoader } from '@/components/ui/Spinner'

interface Props {
  children: React.ReactNode
  allowedRoles?: RoleEnum[]
}

export function ProtectedRoute({ children, allowedRoles }: Props) {
  const { user, isLoading } = useAuth()

  if (isLoading) return <PageLoader />
  if (!user) return <Navigate to="/login" replace />

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <div className="page">
        <div className="alert alert-error">
          Accès refusé — votre rôle ({user.role}) ne permet pas d'accéder à cette page.
        </div>
      </div>
    )
  }

  return <>{children}</>
}
