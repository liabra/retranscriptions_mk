import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { grillesService } from '@/services/grilles.service'
import type { GrilleTarifaire, GrilleCreate, TypeGrille } from '@/types'
import { PageLoader } from '@/components/ui/Spinner'
import { formatDate } from '@/utils/statuts'

const TYPE_GRILLE_LABELS: Record<TypeGrille, string> = {
  client: 'Client',
  retranscripteur: 'Retranscripteur',
  correcteur: 'Correcteur',
  urgence: 'Urgence',
  snp: 'Sans prise de note',
  special: 'Spécial',
  prise_de_note: 'Prise de note',
}

const EMPTY_FORM: GrilleCreate = {
  nom: '',
  type: 'client',
  cible: 'global',
  version: '1.0',
  date_debut: new Date().toISOString().slice(0, 10),
}

export function GrillesPage() {
  const navigate = useNavigate()
  const [grilles, setGrilles] = useState<GrilleTarifaire[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<GrilleCreate>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')

  useEffect(() => {
    grillesService
      .list()
      .then(setGrilles)
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false))
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')
    setSaving(true)
    try {
      const created = await grillesService.create(form)
      setGrilles((prev) => [...prev, created])
      setShowForm(false)
      setForm(EMPTY_FORM)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setFormError(typeof detail === 'string' ? detail : 'Erreur lors de la création')
    } finally {
      setSaving(false)
    }
  }

  async function handleDeactivate(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm('Désactiver cette grille ?')) return
    await grillesService.deactivate(id)
    setGrilles((prev) => prev.map((g) => (g.id === id ? { ...g, active: false } : g)))
  }

  if (isLoading) return <PageLoader />

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Grilles tarifaires</h1>
          <p className="page-subtitle">
            {grilles.length} grille{grilles.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Annuler' : '+ Nouvelle grille'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {showForm && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <h2 className="card-title">Nouvelle grille</h2>
          </div>
          <div className="card-body">
            <form onSubmit={handleCreate}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                <div>
                  <label className="form-label">Nom</label>
                  <input
                    className="form-input"
                    value={form.nom}
                    onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">Type</label>
                  <select
                    className="form-input"
                    value={form.type}
                    onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as TypeGrille }))}
                  >
                    {Object.entries(TYPE_GRILLE_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="form-label">Version</label>
                  <input
                    className="form-input"
                    value={form.version ?? '1.0'}
                    onChange={(e) => setForm((f) => ({ ...f, version: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="form-label">Date début</label>
                  <input
                    className="form-input"
                    type="date"
                    value={form.date_debut}
                    onChange={(e) => setForm((f) => ({ ...f, date_debut: e.target.value }))}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">Date fin (optionnel)</label>
                  <input
                    className="form-input"
                    type="date"
                    value={form.date_fin ?? ''}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, date_fin: e.target.value || undefined }))
                    }
                  />
                </div>
                <div>
                  <label className="form-label">Cible</label>
                  <select
                    className="form-input"
                    value={form.cible ?? 'global'}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        cible: e.target.value as GrilleCreate['cible'],
                      }))
                    }
                  >
                    <option value="global">Globale</option>
                    <option value="client_specifique">Client spécifique</option>
                    <option value="prestataire_specifique">Prestataire spécifique</option>
                  </select>
                </div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <label className="form-label">Description</label>
                  <input
                    className="form-input"
                    value={form.description ?? ''}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, description: e.target.value || undefined }))
                    }
                  />
                </div>
              </div>
              {formError && (
                <div className="alert alert-error" style={{ marginTop: 8 }}>
                  {formError}
                </div>
              )}
              <div style={{ marginTop: 12 }}>
                <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
                  {saving ? '...' : 'Créer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-body" style={{ padding: 0 }}>
          {grilles.length === 0 ? (
            <div
              style={{
                padding: 40,
                textAlign: 'center',
                color: 'var(--color-text-muted)',
                fontSize: 14,
              }}
            >
              Aucune grille tarifaire configurée
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  {['Nom', 'Type', 'Cible', 'Version', 'Début', 'Fin', 'Statut', ''].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: 'left',
                        padding: '10px 12px',
                        fontWeight: 600,
                        fontSize: 11,
                        color: 'var(--color-text-muted)',
                        textTransform: 'uppercase',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grilles.map((g) => (
                  <tr
                    key={g.id}
                    style={{
                      borderBottom: '1px solid var(--color-border-light)',
                      cursor: 'pointer',
                    }}
                    onClick={() => navigate(`/grilles/${g.id}`)}
                  >
                    <td style={{ padding: '10px 12px', fontWeight: 500 }}>{g.nom}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span className="badge badge-blue">{TYPE_GRILLE_LABELS[g.type]}</span>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {g.cible === 'global' ? '—' : g.cible}
                    </td>
                    <td style={{ padding: '10px 12px' }}>{g.version}</td>
                    <td style={{ padding: '10px 12px' }}>{formatDate(g.date_debut)}</td>
                    <td style={{ padding: '10px 12px' }}>{formatDate(g.date_fin)}</td>
                    <td style={{ padding: '10px 12px' }}>
                      {g.active ? (
                        <span className="badge badge-green">Active</span>
                      ) : (
                        <span className="badge badge-gray">Inactive</span>
                      )}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {g.active && (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: 'var(--color-danger)', fontSize: 11 }}
                          onClick={(e) => handleDeactivate(g.id, e)}
                        >
                          Désactiver
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
