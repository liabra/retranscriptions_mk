import { useEffect, useState } from 'react'
import { clientsService } from '@/services/clients.service'
import type { Client, ClientCreate, TypeClient } from '@/types'
import { PageLoader, Spinner } from '@/components/ui/Spinner'
import { getApiErrorMessage } from '@/services/api'

const TYPE_CLIENTS: TypeClient[] = ['CE', 'CMAS', 'CSSCT', 'Syndicat', 'Autre']

function ClientModal({
  onClose,
  onSaved,
  initial,
}: {
  onClose: () => void
  onSaved: (c: Client) => void
  initial?: Client
}) {
  const [form, setForm] = useState<ClientCreate>({
    nom: initial?.nom ?? '',
    type: initial?.type ?? 'CE',
    entreprise_mere: initial?.entreprise_mere ?? '',
    contact_principal: initial?.contact_principal ?? '',
    email_contact: initial?.email_contact ?? '',
    telephone: initial?.telephone ?? '',
    conditions_paiement: initial?.conditions_paiement ?? '',
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const saved = initial
        ? await clientsService.update(initial.id, form)
        : await clientsService.create(form)
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
          <h2 className="modal-title">{initial ? 'Modifier client' : 'Nouveau client'}</h2>
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
                <label className="form-label">Type <span className="req">*</span></label>
                <select className="form-select" value={form.type} onChange={(e) => set('type', e.target.value)}>
                  {TYPE_CLIENTS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Entreprise mère</label>
              <input className="form-input" value={form.entreprise_mere} onChange={(e) => set('entreprise_mere', e.target.value)} />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Contact principal</label>
                <input className="form-input" value={form.contact_principal} onChange={(e) => set('contact_principal', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Email</label>
                <input className="form-input" type="email" value={form.email_contact} onChange={(e) => set('email_contact', e.target.value)} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Téléphone</label>
                <input className="form-input" value={form.telephone} onChange={(e) => set('telephone', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Conditions paiement</label>
                <input className="form-input" value={form.conditions_paiement} onChange={(e) => set('conditions_paiement', e.target.value)} placeholder="Ex : 30 jours fin de mois" />
              </div>
            </div>
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

export function ClientsListPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Client | undefined>()

  useEffect(() => {
    clientsService.list(false)
      .then(setClients)
      .catch(console.error)
      .finally(() => setIsLoading(false))
  }, [])

  function handleSaved(c: Client) {
    setClients((prev) => {
      const idx = prev.findIndex((p) => p.id === c.id)
      if (idx >= 0) { const next = [...prev]; next[idx] = c; return next }
      return [...prev, c]
    })
    setShowModal(false)
    setEditing(undefined)
  }

  if (isLoading) return <PageLoader />

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Clients</h1>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
            {clients.filter((c) => c.actif).length} client{clients.filter((c) => c.actif).length > 1 ? 's' : ''} actifs
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => { setEditing(undefined); setShowModal(true) }}>
          + Nouveau client
        </button>
      </div>

      <div className="card">
        {clients.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🏢</div>
            <div className="empty-state-text">Aucun client enregistré</div>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Nom</th>
                  <th>Type</th>
                  <th>Entreprise mère</th>
                  <th>Contact</th>
                  <th>Statut</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {clients.map((c) => (
                  <tr key={c.id}>
                    <td><strong>{c.nom}</strong></td>
                    <td><span className="badge badge-blue">{c.type}</span></td>
                    <td className="td-muted">{c.entreprise_mere ?? '—'}</td>
                    <td className="td-muted">{c.contact_principal ?? '—'}</td>
                    <td>
                      {c.actif
                        ? <span className="badge badge-green">Actif</span>
                        : <span className="badge badge-gray">Inactif</span>
                      }
                    </td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => { setEditing(c); setShowModal(true) }}>
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
        <ClientModal
          initial={editing}
          onClose={() => { setShowModal(false); setEditing(undefined) }}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
