import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthContext'
import { ROLE_LABELS } from '@/utils/statuts'
import { HintsProvider, useHints } from '@/contexts/HintsContext'

// Nav commune à tous (sauf prestataires qui ont la leur)
const NAV_ITEMS = [
  { to: '/dashboard', icon: '◻', label: 'Dashboard' },
  { to: '/dossiers', icon: '📋', label: 'Dossiers' },
  { to: '/clients', icon: '🏢', label: 'Clients' },
  { to: '/prestataires', icon: '👤', label: 'Prestataires' },
  { to: '/aide', icon: '?', label: 'Aide' },
]

const ADMIN_NAV = [
  { to: '/utilisateurs', icon: '👥', label: 'Utilisateurs' },
  { to: '/grilles', icon: '⚙', label: 'Grilles tarifaires' },
]

// Nav exclusive pour retranscripteur/correcteur — remplace NAV_ITEMS
const PRESTATAIRE_NAV = [
  { to: '/mes-dossiers', icon: '✓', label: 'Mes missions' },
  { to: '/aide', icon: '?', label: 'Aide' },
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
  const isAdminOrCoord = user?.role === 'administratrice' || user?.role === 'coordinatrice'

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-title">Retranscriptions</div>
          <div className="sidebar-logo-sub">CE · CMAS · CSSCT</div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-title">Navigation</div>
          {(isPrestataire ? PRESTATAIRE_NAV : NAV_ITEMS).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              <em className="nav-link-icon">{item.icon}</em>
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
                  <em className="nav-link-icon">{item.icon}</em>
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
