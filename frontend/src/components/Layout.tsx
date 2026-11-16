import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Bell, BookOpen, Building2, ClipboardList, FolderOpen, Gauge, History, LogOut, Menu, Mic, Receipt,
  Settings, SlidersHorizontal, UserCog, Users, Upload, type LucideIcon,
} from 'lucide-react'
import { useAuth } from '@/lib/session'
import { api, type Notif } from '@/lib/api'
import { fDateTime, initials, ROLES } from '@/lib/format'

interface NavItem { to: string; label: string; icon: LucideIcon; perm?: string; any?: string[] }

const INTERNE: { group: string; items: NavItem[] }[] = [
  { group: 'Pilotage', items: [
    { to: '/tableau-de-bord', label: 'Tableau de bord', icon: Gauge },
    { to: '/audios', label: 'Audios reçus', icon: Mic, perm: 'audios.gerer' },
    { to: '/dossiers', label: 'Dossiers', icon: FolderOpen, perm: 'dossiers.voir' },
    { to: '/finance', label: 'Facturation', icon: Receipt, perm: 'finance.voir' },
  ] },
  { group: 'Référentiels', items: [
    { to: '/clients', label: 'Clients & instances', icon: Building2, any: ['clients.gerer', 'dossiers.voir'] },
    { to: '/retranscripteurs', label: 'Retranscripteurs', icon: Users, any: ['prestataires.gerer', 'attribution.gerer'] },
    { to: '/tarifs', label: 'Tarifs & paramètres', icon: SlidersHorizontal, any: ['tarifs.gerer', 'finance.voir'] },
  ] },
  { group: 'Administration', items: [
    { to: '/utilisateurs', label: 'Utilisateurs & droits', icon: UserCog, perm: 'utilisateurs.gerer' },
    { to: '/journal', label: "Journal d'activité", icon: History, perm: 'journal.voir' },
    { to: '/aide', label: 'Aide', icon: BookOpen },
  ] },
]

const PRESTATAIRE: NavItem[] = [
  { to: '/mes-missions', label: 'Mes missions', icon: ClipboardList },
  { to: '/aide', label: 'Aide', icon: BookOpen },
]
const CLIENT: NavItem[] = [{ to: '/mon-espace', label: 'Mon espace', icon: Upload }]

export function Layout() {
  const { user, can, isPrestataire, isClient, logout } = useAuth()
  const [scrolled, setScrolled] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  // Le menu mobile se referme de lui-même à chaque changement de page
  const [openAt, setOpenAt] = useState<string | null>(null)
  const open = openAt === location.pathname
  const setOpen = (v: boolean) => setOpenAt(v ? location.pathname : null)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const visible = (i: NavItem) => (!i.perm || can(i.perm)) && (!i.any || i.any.some(can))
  const groups = isPrestataire ? [{ group: 'Mon travail', items: PRESTATAIRE }]
    : isClient ? [{ group: 'Mon espace', items: CLIENT }] : INTERNE

  return (
    <div className="shell">
      <div className={`backdrop${open ? ' open' : ''}`} onClick={() => setOpen(false)} />
      <aside className={`sidebar${open ? ' open' : ''}`} aria-label="Navigation principale">
        <div className="brand">
          <div className="brand-mark" aria-hidden>A2C</div>
          <div>
            <div className="brand-name">A2C</div>
            <div className="brand-sub">Retranscriptions</div>
          </div>
        </div>
        <nav>
          {groups.map((g) => {
            const items = g.items.filter(visible)
            if (!items.length) return null
            return (
              <div key={g.group}>
                <div className="nav-group">{g.group}</div>
                {items.map((i) => (
                  <NavLink key={i.to} to={i.to} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
                    <i.icon size={19} strokeWidth={1.8} />{i.label}
                  </NavLink>
                ))}
              </div>
            )
          })}
        </nav>
        <div className="sidebar-foot">
          <NavLink to="/compte" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            <Settings size={19} strokeWidth={1.8} />Mon compte
          </NavLink>
          <button className="nav-link btn-ghost" style={{ width: '100%', border: 0, cursor: 'pointer', background: 'none' }}
            onClick={() => { logout(); navigate('/login') }}>
            <LogOut size={19} strokeWidth={1.8} />Se déconnecter
          </button>
        </div>
      </aside>

      <div className="main">
        <header className={`topbar${scrolled ? ' scrolled' : ''}`}>
          <button className="btn btn-ghost btn-icon menu-btn" onClick={() => setOpen(true)} aria-label="Ouvrir le menu">
            <Menu size={20} />
          </button>
          <div className="topbar-spacer" />
          <Notifications />
          <div className="row" style={{ gap: 10 }}>
            <div className="avatar" aria-hidden>{initials(user?.nom)}</div>
            <div style={{ lineHeight: 1.2 }} className="hide-sm">
              <div style={{ fontWeight: 600, fontSize: 14 }}>{user?.nom}</div>
              <div className="small muted">{ROLES[user?.role ?? ''] ?? user?.role}</div>
            </div>
          </div>
        </header>
        <main className="content" id="contenu">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function Notifications() {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<{ non_lues: number; items: Notif[] } | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const load = () => api.notifications().then(setData).catch(() => undefined)
  useEffect(() => {
    load()
    const t = window.setInterval(load, 60000)
    return () => window.clearInterval(t)
  }, [])
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const ouvrir = async (n: Notif) => {
    if (!n.lu) await api.lireNotif(n.id).catch(() => undefined)
    setOpen(false)
    load()
    if (n.lien?.startsWith('/')) navigate(n.lien)
  }

  return (
    <div className="bell" ref={ref} style={{ position: 'relative' }}>
      <button className="btn btn-ghost btn-icon" aria-label={`Notifications${data?.non_lues ? ` (${data.non_lues} non lues)` : ''}`}
        onClick={() => { setOpen(!open); if (!open) load() }}>
        <Bell size={20} />
      </button>
      {!!data?.non_lues && <span className="bell-count">{data.non_lues > 99 ? '99+' : data.non_lues}</span>}
      {open && (
        <div className="popover" role="dialog" aria-label="Notifications">
          <div className="header-row" style={{ padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
            <strong>Notifications</strong>
            {!!data?.non_lues && (
              <button className="btn btn-ghost btn-sm" onClick={() => api.toutLire().then(load)}>Tout marquer comme lu</button>
            )}
          </div>
          <div style={{ maxHeight: 420, overflowY: 'auto' }}>
            {!data?.items.length && <div className="empty small">Aucune notification pour le moment.</div>}
            {data?.items.map((n) => (
              <div key={n.id} className={`notif${n.lu ? '' : ' unread'}`} onClick={() => ouvrir(n)}
                role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') ouvrir(n) }}>
                <span className="notif-dot" />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{n.titre}</div>
                  {n.message && <div className="small muted" style={{ marginTop: 2 }}>{n.message}</div>}
                  <div className="small" style={{ color: 'var(--faint)', marginTop: 4 }}>{fDateTime(n.created_at)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
