import { useEffect, useState } from 'react'
import { prestatairesService } from '@/services/prestataires.service'
import type { Prestataire, PrestaCreate, RolePresta } from '@/types'
import { PageLoader, Spinner } from '@/components/ui/Spinner'
import { getApiErrorMessage } from '@/services/api'

const ROLE_LABELS: Record<RolePresta, string> = {
  retranscripteur: 'Retranscripteur',
  correcteur: 'Correcteur',
  les_deux: 'Retranscripteur + Correcteur',
}

function PrestaModal({
  onClose,
  onSaved,
  initial,
}: {
  onClose: () => void
  onSaved: (p: Prestataire) => void
  initial?: Prestataire
}) {
  const [form, setForm] = useState<PrestaCreate>({
    nom: initial?.nom ?? '',
    role: initial?.role ?? 'retranscripteur',
    email: initial?.email ?? '',
    telephone: initial?.telephone ?? '',
    disponible: initial?.disponible ?? true,
    iban: '',  // jamais pré-rempli — sécurité
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  function set(field: string, value: string | boolean) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const payload = { ...form }
      if (!payload.iban) delete payload.iban  // ne pas écraser si vide
      const saved = initial
        ? await prestatairesService.update(initial.id, payload)
        : await prestatairesService.create(payload)
      onSaved(saved)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{initial ? 'Modifier prestataire' : 'Nouveau prestataire'}</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && <div className="alert alert-error">{error}</div>}

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Nom <span className="req">*</span></label>
                <input className="form-input" value={form.nom} onChange={(e) => set('nom', e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label">Rôle <span className="req">*</span></label>
                <select className="form-select" value={form.role} onChange={(e) => set('role', e.target.value)}>
                  {(Object.entries(ROLE_LABELS) as [RolePresta, string][]).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Email <span className="req">*</span></label>
                <input className="form-input" type="email" value={form.email} onChange={(e) => set('email', e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label">Téléphone</label>
                <input className="form-input" value={form.telephone} onChange={(e) => set('telephone', e.target.value)} />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">IBAN {initial ? '(laisser vide pour ne pas modifier)' : ''}</label>
              <input
                className="form-input"
                value={form.iban}
                onChange={(e) => set('iban', e.target.value)}
                placeholder="FR76 xxxx xxxx xxxx xxxx xxxx xxx"
                autoComplete="off"
              />
              <span className="form-hint">Stocké chiffré (AES-256) — jamais visible en clair dans l'interface</span>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.disponible} onChange={(e) => set('disponible', e.target.checked)} />
              Disponible pour nouvelles affectations
            </label>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Annuler</button>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? <Spinner size={14} /> : null}
              {isSubmitting ? 'Enregistrement…' : (initial ? 'Mettre à jour' : 'Créer')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export function PrestatairesListPage() {
  const [prestataires, setPrestataires] = useState<Prestataire[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Prestataire | undefined>()

  useEffect(() => {
    prestatairesService.list({ actif_only: false })
      .then(setPrestataires)
      .catch(console.error)
      .finally(() => setIsLoading(false))
  }, [])

  function handleSaved(p: Prestataire) {
    setPrestataires((prev) => {
      const idx = prev.findIndex((x) => x.id === p.id)
      if (idx >= 0) { const next = [...prev]; next[idx] = p; return next }
      return [...prev, p]
    })
    setShowModal(false)
    setEditing(undefined)
  }

  async function toggleDisponible(p: Prestataire) {
    const updated = await prestatairesService.update(p.id, { disponible: !p.disponible })
    setPrestataires((prev) => prev.map((x) => x.id === p.id ? updated : x))
  }

  if (isLoading) return <PageLoader />

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Prestataires</h1>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
            {prestataires.filter((p) => p.disponible && p.actif).length} disponibles
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => { setEditing(undefined); setShowModal(true) }}>
          + Nouveau prestataire
        </button>
      </div>

      <div className="card">
        {prestataires.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <div className="empty-state-text">Aucun prestataire enregistré</div>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Nom</th>
                  <th>Rôle</th>
                  <th>Email</th>
                  <th>Charge</th>
                  <th>Qualité</th>
                  <th>Dispo</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {prestataires.map((p) => (
                  <tr key={p.id} style={{ opacity: p.actif ? 1 : 0.5 }}>
                    <td><strong>{p.nom}</strong></td>
                    <td><span className="badge badge-blue">{ROLE_LABELS[p.role]}</span></td>
                    <td className="td-muted">{p.email}</td>
                    <td className="td-muted">{p.charge_actuelle} dossier{p.charge_actuelle > 1 ? 's' : ''}</td>
                    <td>
                      <span
                        className={`badge ${parseFloat(p.note_qualite) >= 0.9 ? 'badge-green' : parseFloat(p.note_qualite) >= 0.7 ? 'badge-yellow' : 'badge-red'}`}
                      >
                        {(parseFloat(p.note_qualite) * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td>
                      <button
                        className={`badge ${p.disponible ? 'badge-green' : 'badge-gray'}`}
                        style={{ cursor: 'pointer', border: 'none' }}
                        onClick={() => toggleDisponible(p)}
                        title="Cliquer pour basculer"
                      >
                        {p.disponible ? 'Disponible' : 'Indisponible'}
                      </button>
                    </td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => { setEditing(p); setShowModal(true) }}>
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

      {showModal && (
        <PrestaModal
          initial={editing}
          onClose={() => { setShowModal(false); setEditing(undefined) }}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
