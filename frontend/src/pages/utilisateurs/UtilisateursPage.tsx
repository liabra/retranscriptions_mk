import { useEffect, useState } from 'react'
import { usersService } from '@/services/users.service'
import type { User, RoleEnum } from '@/types'
import { PageLoader, Spinner } from '@/components/ui/Spinner'
import { getApiErrorMessage } from '@/services/api'
import { ROLE_LABELS } from '@/utils/statuts'
import { formatDate } from '@/utils/statuts'

const ALL_ROLES: RoleEnum[] = [
  'administratrice',
  'coordinatrice',
  'retranscripteur',
  'correcteur',
  'comptabilite',
  'lecture_seule',
]

const ROLE_BADGE: Record<RoleEnum, string> = {
  administratrice: 'badge-red',
  coordinatrice: 'badge-blue',
  retranscripteur: 'badge-orange',
  correcteur: 'badge-orange',
  comptabilite: 'badge-green',
  lecture_seule: 'badge-gray',
}

// ─── Modal création ───────────────────────────────────────────────────────────

function CreateUserModal({ onClose, onSaved }: { onClose: () => void; onSaved: (u: User) => void }) {
  const [form, setForm] = useState({ email: '', nom: '', password: '', role: 'retranscripteur' as RoleEnum })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const user = await usersService.create(form)
      onSaved(user)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Nouveau compte utilisateur</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && <div className="alert alert-error">{error}</div>}
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Nom <span className="req">*</span></label>
                <input className="form-input" value={form.nom}
                  onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))} required />
              </div>
              <div className="form-group">
                <label className="form-label">Rôle <span className="req">*</span></label>
                <select className="form-select" value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as RoleEnum }))}>
                  {ALL_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Email <span className="req">*</span></label>
              <input className="form-input" type="email" value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} required />
            </div>
            <div className="form-group">
              <label className="form-label">Mot de passe <span className="req">*</span></label>
              <input className="form-input" type="password" value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                autoComplete="new-password" required minLength={8} />
              <span className="form-hint">8 caractères minimum</span>
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Annuler</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? <Spinner size={14} /> : null}
              {saving ? 'Création…' : 'Créer le compte'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Modal édition ────────────────────────────────────────────────────────────

function EditUserModal({ user, onClose, onSaved }: { user: User; onClose: () => void; onSaved: (u: User) => void }) {
  const [nom, setNom] = useState(user.nom)
  const [role, setRole] = useState<RoleEnum>(user.role)
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload: { nom?: string; role?: RoleEnum; password?: string } = {}
      if (nom !== user.nom) payload.nom = nom
      if (role !== user.role) payload.role = role
      if (password) payload.password = password
      const updated = await usersService.update(user.id, payload)
      onSaved(updated)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleToggleActif() {
    if (!confirm(`${user.actif ? 'Désactiver' : 'Réactiver'} le compte de ${user.nom} ?`)) return
    setSaving(true)
    try {
      const updated = await usersService.update(user.id, { actif: !user.actif })
      onSaved(updated)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Modifier — {user.nom}</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && <div className="alert alert-error">{error}</div>}
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Nom</label>
                <input className="form-input" value={nom} onChange={(e) => setNom(e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label">Rôle</label>
                <select className="form-select" value={role} onChange={(e) => setRole(e.target.value as RoleEnum)}>
                  {ALL_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input className="form-input" value={user.email} disabled style={{ opacity: 0.6 }} />
              <span className="form-hint">L'email ne peut pas être modifié</span>
            </div>
            <div className="form-group">
              <label className="form-label">Nouveau mot de passe</label>
              <input className="form-input" type="password" value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password" minLength={8}
                placeholder="Laisser vide pour ne pas changer" />
            </div>
          </div>
          <div className="modal-footer" style={{ justifyContent: 'space-between' }}>
            <button
              type="button"
              className="btn btn-secondary"
              style={user.actif ? { color: 'var(--color-danger)', borderColor: 'var(--color-danger)' } : {}}
              onClick={handleToggleActif}
              disabled={saving}
            >
              {user.actif ? 'Désactiver le compte' : 'Réactiver le compte'}
            </button>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="button" className="btn btn-secondary" onClick={onClose}>Annuler</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? <Spinner size={14} /> : null}
                {saving ? 'Enregistrement…' : 'Enregistrer'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Page principale ──────────────────────────────────────────────────────────

export function UtilisateursPage() {
  const [users, setUsers] = useState<User[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<User | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    usersService.list()
      .then(setUsers)
      .catch((e) => setError(getApiErrorMessage(e)))
      .finally(() => setIsLoading(false))
  }, [])

  function handleSaved(u: User) {
    setUsers((prev) => {
      const idx = prev.findIndex((x) => x.id === u.id)
      if (idx >= 0) { const next = [...prev]; next[idx] = u; return next }
      return [...prev, u]
    })
    setShowCreate(false)
    setEditing(null)
  }

  const actifs = users.filter((u) => u.actif)
  const inactifs = users.filter((u) => !u.actif)

  if (isLoading) return <PageLoader />

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Utilisateurs</h1>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
            {actifs.length} compte{actifs.length > 1 ? 's' : ''} actif{actifs.length > 1 ? 's' : ''}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + Nouveau compte
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        {users.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <div className="empty-state-text">Aucun utilisateur</div>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Nom</th>
                  <th>Email</th>
                  <th>Rôle</th>
                  <th>Statut</th>
                  <th>Créé le</th>
                  <th>Dernière connexion</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {[...actifs, ...inactifs].map((u) => (
                  <tr key={u.id} style={{ opacity: u.actif ? 1 : 0.5 }}>
                    <td><strong>{u.nom}</strong></td>
                    <td className="td-muted">{u.email}</td>
                    <td><span className={`badge ${ROLE_BADGE[u.role]}`}>{ROLE_LABELS[u.role]}</span></td>
                    <td>
                      {u.actif
                        ? <span className="badge badge-green">Actif</span>
                        : <span className="badge badge-gray">Désactivé</span>
                      }
                    </td>
                    <td className="td-muted">{formatDate(u.created_at)}</td>
                    <td className="td-muted">{u.last_login ? formatDate(u.last_login) : '—'}</td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => setEditing(u)}>
                        Modifier
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onSaved={handleSaved}
        />
      )}
      {editing && (
        <EditUserModal
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
