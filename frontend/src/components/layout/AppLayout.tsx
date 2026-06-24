import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthContext'
import { ROLE_LABELS } from '@/utils/statuts'
import { HintsProvider, useHints } from '@/contexts/HintsContext'

function Icon({ path, size = 18 }: { path: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  )
}

// Nav commune à tous (sauf prestataires qui ont la leur)
const NAV_ITEMS = [
  { to: '/dashboard',    icon: 'M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z', label: 'Dashboard' },
  { to: '/dossiers',     icon: 'M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z', label: 'Dossiers' },
  { to: '/clients',      icon: 'M3 21h18 M5 21V7l7-4 7 4v14 M9 9h.01 M9 13h.01 M9 17h.01 M15 9h.01 M15 13h.01 M15 17h.01', label: 'Clients' },
  { to: '/prestataires', icon: 'M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2 M12 11a4 4 0 100-8 4 4 0 000 8z', label: 'Prestataires' },
  { to: '/aide',         icon: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M9.1 9a3 3 0 015.8 1c0 2-3 3-3 3 M12 17h.01', label: 'Aide' },
]

const ADMIN_NAV = [
  { to: '/utilisateurs', icon: 'M17 21v-2a4 4 0 00-3-3.87 M9 21v-2a4 4 0 013-3.87 M13 7a4 4 0 11-8 0 4 4 0 018 0z M16 3.13a4 4 0 010 7.75 M22 21v-2a4 4 0 00-3-3.87', label: 'Utilisateurs' },
  { to: '/grilles',      icon: 'M4 21v-7 M4 10V3 M12 21v-9 M12 8V3 M20 21v-5 M20 12V3 M1 14h6 M9 8h6 M17 16h6', label: 'Grilles tarifaires' },
]

// Nav exclusive pour retranscripteur/correcteur — remplace NAV_ITEMS
const PRESTATAIRE_NAV = [
  { to: '/mes-dossiers', icon: 'M9 11l3 3L22 4 M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11', label: 'Mes missions' },
  { to: '/aide',         icon: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M9.1 9a3 3 0 015.8 1c0 2-3 3-3 3 M12 17h.01', label: 'Aide' },
]

// Nav exclusive pour les clients
const CLIENT_NAV = [
  { to: '/mon-espace',   icon: 'M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z M19 10v2a7 7 0 01-14 0v-2 M12 19v4 M8 23h8', label: 'Mon espace' },
]

export function AppLayout() {
  return (
    <HintsProvider>
      <AppLayoutInner />
    </HintsProvider>
  )
}

function AppLayoutInner() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { enabled: hintsEnabled, toggle: toggleHints } = useHints()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  const isPrestataire = user?.role === 'retranscripteur' || user?.role === 'correcteur'
  const isClient      = user?.role === 'client'
  const isAdminOrCoord = user?.role === 'administratrice' || user?.role === 'coordinatrice'

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-title">A2C</div>
          <div className="sidebar-logo-sub">Retranscription</div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-title">Navigation</div>
          {(isPrestataire ? PRESTATAIRE_NAV : isClient ? CLIENT_NAV : NAV_ITEMS).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              <span className="nav-link-icon"><Icon path={item.icon} /></span>
              {item.label}
            </NavLink>
          ))}

          {isAdminOrCoord && (
            <>
              <div className="nav-section-title" style={{ marginTop: 8 }}>Administration</div>
              {ADMIN_NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                >
                  <span className="nav-link-icon"><Icon path={item.icon} /></span>
                  {item.label}
                </NavLink>
              ))}
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user-name">{user?.nom}</div>
          <div className="sidebar-user-role">{user ? ROLE_LABELS[user.role] : ''}</div>
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginTop: 8, width: '100%', justifyContent: 'flex-start', color: 'rgba(255,255,255,.5)', padding: '4px 0' }}
            onClick={toggleHints}
            title={hintsEnabled ? 'Masquer les conseils contextuels' : 'Afficher les conseils contextuels'}
          >
            {hintsEnabled ? '💡 Masquer les conseils' : '💡 Afficher les conseils'}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginTop: 4, width: '100%', justifyContent: 'flex-start', color: 'rgba(255,255,255,.5)', padding: '4px 0' }}
            onClick={handleLogout}
          >
            Déconnexion
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
