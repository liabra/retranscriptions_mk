import { createBrowserRouter, Navigate } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { ProtectedRoute } from './ProtectedRoute'

import { LoginPage } from '@/pages/auth/LoginPage'
import { DashboardPage } from '@/pages/dashboard/DashboardPage'
import { DossiersListPage } from '@/pages/dossiers/DossiersListPage'
import { DossierCreatePage } from '@/pages/dossiers/DossierCreatePage'
import { DossierDetailPage } from '@/pages/dossiers/DossierDetailPage'
import { ClientsListPage } from '@/pages/clients/ClientsListPage'
import { PrestatairesListPage } from '@/pages/prestataires/PrestatairesListPage'
import { GrillesPage } from '@/pages/grilles/GrillesPage'
import { GrilleDetailPage } from '@/pages/grilles/GrilleDetailPage'
import { MissionsPage } from '@/pages/missions/MissionsPage'
import { UtilisateursPage } from '@/pages/utilisateurs/UtilisateursPage'
import { AidePage } from '@/pages/aide/AidePage'
import { MesDossiersPage } from '@/pages/prestataires/MesDossiersPage'
import { MonEspaceClientPage } from '@/pages/client/MonEspaceClientPage'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      {
        path: 'dossiers',
        children: [
          { index: true, element: <DossiersListPage /> },
          {
            path: 'nouveau',
            element: (
              <ProtectedRoute allowedRoles={['administratrice', 'coordinatrice']}>
                <DossierCreatePage />
              </ProtectedRoute>
            ),
          },
          { path: ':id', element: <DossierDetailPage /> },
        ],
      },
      {
        path: 'clients',
        element: (
          <ProtectedRoute allowedRoles={['administratrice', 'coordinatrice']}>
            <ClientsListPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'prestataires',
        element: (
          <ProtectedRoute allowedRoles={['administratrice', 'coordinatrice']}>
            <PrestatairesListPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'grilles',
        children: [
          {
            index: true,
            element: (
              <ProtectedRoute allowedRoles={['administratrice', 'coordinatrice']}>
                <GrillesPage />
              </ProtectedRoute>
            ),
          },
          {
            path: ':id',
            element: (
              <ProtectedRoute allowedRoles={['administratrice', 'coordinatrice']}>
                <GrilleDetailPage />
              </ProtectedRoute>
            ),
          },
        ],
      },
      { path: 'missions', element: <MissionsPage /> },
      { path: 'aide', element: <AidePage /> },
      {
        path: 'mes-dossiers',
        element: (
          <ProtectedRoute allowedRoles={['retranscripteur', 'correcteur']}>
            <MesDossiersPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'mon-espace',
        element: (
          <ProtectedRoute allowedRoles={['client']}>
            <MonEspaceClientPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'utilisateurs',
        element: (
          <ProtectedRoute allowedRoles={['administratrice']}>
            <UtilisateursPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
])
