import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { Accueil, Guard, Session, type Rule } from '@/components/Guards'
import { PageLoader } from '@/components/ui'
import { Layout } from '@/components/Layout'
import { LoginPage } from '@/pages/LoginPage'
import { MotDePassePage } from '@/pages/MotDePassePage'
import { DashboardPage } from '@/pages/DashboardPage'
import { DossiersPage } from '@/pages/DossiersPage'
import { ClientsPage, RetranscripteursPage } from '@/pages/ReferentielsPages'
import { AidePage, ComptePage, JournalPage, UtilisateursPage } from '@/pages/AdminPages'
import { EspaceClientPage, MesMissionsPage } from '@/pages/EspacesPages'

const DossierPage = lazy(() => import('@/pages/dossier/DossierPage').then((m) => ({ default: m.DossierPage })))
const AudiosPage = lazy(() => import('@/pages/AudiosPage').then((m) => ({ default: m.AudiosPage })))
const FinancePage = lazy(() => import('@/pages/FinancePage').then((m) => ({ default: m.FinancePage })))
const TarifsPage = lazy(() => import('@/pages/tarifs/TarifsPage').then((m) => ({ default: m.TarifsPage })))
const GrilleDetailPage = lazy(() => import('@/pages/grilles/GrilleDetailPage').then((m) => ({ default: m.GrilleDetailPage })))

const g = (rule: Rule, el: ReactNode, perm?: string[]) => (
  <Guard rule={rule} perm={perm}><Suspense fallback={<PageLoader />}>{el}</Suspense></Guard>
)

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/mot-de-passe', element: <Session><MotDePassePage /></Session> },
  {
    path: '/',
    element: <Session><Layout /></Session>,
    children: [
      { index: true, element: <Accueil /> },
      { path: 'tableau-de-bord', element: g('interne', <DashboardPage />) },
      { path: 'audios', element: g('interne', <AudiosPage />, ['audios.gerer']) },
      { path: 'dossiers', element: g('interne', <DossiersPage />, ['dossiers.voir']) },
      { path: 'dossiers/:id', element: g('interne', <DossierPage />, ['dossiers.voir']) },
      { path: 'finance', element: g('interne', <FinancePage />, ['finance.voir']) },
      { path: 'clients', element: g('interne', <ClientsPage />, ['clients.gerer', 'dossiers.voir']) },
      { path: 'retranscripteurs', element: g('interne', <RetranscripteursPage />, ['prestataires.gerer', 'attribution.gerer']) },
      { path: 'tarifs', element: g('interne', <TarifsPage />, ['tarifs.gerer', 'finance.voir']) },
      { path: 'grilles', element: <Navigate to="/tarifs" replace /> },
      { path: 'grilles/:id', element: g('interne', <GrilleDetailPage />, ['tarifs.gerer', 'finance.voir']) },
      { path: 'utilisateurs', element: g('interne', <UtilisateursPage />, ['utilisateurs.gerer']) },
      { path: 'journal', element: g('interne', <JournalPage />, ['journal.voir']) },
      { path: 'mes-missions', element: g('prestataire', <MesMissionsPage />) },
      { path: 'mon-espace', element: g('client', <EspaceClientPage />) },
      { path: 'compte', element: g('tous', <ComptePage />) },
      { path: 'aide', element: g('tous', <AidePage />) },
      { path: '*', element: <Accueil /> },
    ],
  },
])
