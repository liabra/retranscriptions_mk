import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { grillesService } from '@/services/grilles.service'
import { clientsService } from '@/services/clients.service'
import { prestatairesService } from '@/services/prestataires.service'
import type { GrilleTarifaire, GrilleCreate, TypeGrille, Client, Prestataire } from '@/types'
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
  const [clients, setClients] = useState<Client[]>([])
  const [prestataires, setPrestataires] = useState<Prestataire[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<GrilleCreate>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')

  // Lookup maps for cible_id resolution in the table
  const clientMap = Object.fromEntries(clients.map((c) => [c.id, c.nom]))
  const prestaMap = Object.fromEntries(prestataires.map((p) => [p.id, p.nom]))

  useEffect(() => {
    Promise.all([
      grillesService.list(),
      clientsService.list(false),
      prestatairesService.list({ actif_only: false }),
    ])
      .then(([g, c, p]) => {
        setGrilles(g)
        setClients(c)
        setPrestataires(p)
      })
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

  async function handleReactivate(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    await grillesService.update(id, { active: true })
    setGrilles((prev) => prev.map((g) => (g.id === id ? { ...g, active: true } : g)))
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
            <h2 className="card-title">Nouvelle grille tarifaire</h2>
          </div>
          <div className="card-body">
            {/* Explication contextuelle */}
            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 'var(--radius)', padding: '10px 14px', marginBottom: 16, fontSize: 12, color: '#1e40af', lineHeight: 1.6 }}>
              ℹ️ Une grille définit le taux de rémunération des prestataires (retranscripteur, correcteur) ou les majorations (urgence).
              Les grilles <strong>globales</strong> s'appliquent à tous les dossiers. Les grilles <strong>spécifiques</strong> s'appliquent à un client ou prestataire particulier et ont la priorité.
              <br />Après création, vous pourrez ajouter les règles de calcul (taux, majorations...) depuis la fiche de la grille.
            </div>
            <form onSubmit={handleCreate}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                <div>
                  <label className="form-label">Nom de la grille <span style={{ color: 'var(--color-danger)' }}>*</span></label>
                  <input
                    className="form-input"
                    placeholder="ex: Tarif retranscripteur 2026"
                    value={form.nom}
                    onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">
                    À quoi sert cette grille ? <span style={{ color: 'var(--color-danger)' }}>*</span>
                  </label>
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
                  <label className="form-label">
                    S'applique à…
                  </label>
                  <select
                    className="form-input"
                    value={form.cible ?? 'global'}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        cible: e.target.value as GrilleCreate['cible'],
                        cible_id: undefined,
                      }))
                    }
                  >
                    <option value="global">Tous les dossiers (globale)</option>
                    <option value="client_specifique">Un client spécifique</option>
                    <option value="prestataire_specifique">Un prestataire spécifique</option>
                  </select>
                </div>
                {form.cible === 'client_specifique' && (
                  <div>
                    <label className="form-label">Client</label>
                    <select
                      className="form-input"
                      value={form.cible_id ?? ''}
                      onChange={(e) => setForm((f) => ({ ...f, cible_id: e.target.value || undefined }))}
                      required
                    >
                      <option value="">— Sélectionner —</option>
                      {clients.map((c) => (
                        <option key={c.id} value={c.id}>{c.nom}</option>
                      ))}
                    </select>
                  </div>
                )}
                {form.cible === 'prestataire_specifique' && (
                  <div>
                    <label className="form-label">Prestataire</label>
                    <select
                      className="form-input"
                      value={form.cible_id ?? ''}
                      onChange={(e) => setForm((f) => ({ ...f, cible_id: e.target.value || undefined }))}
                      required
                    >
                      <option value="">— Sélectionner —</option>
                      {prestataires.map((p) => (
                        <option key={p.id} value={p.id}>{p.nom}</option>
                      ))}
                    </select>
                  </div>
                )}
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
                      {g.cible === 'global'
                        ? '—'
                        : g.cible === 'client_specifique'
                        ? clientMap[g.cible_id ?? ''] ?? 'Client spécifique'
                        : prestaMap[g.cible_id ?? ''] ?? 'Prestataire spécifique'}
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
                      {g.active ? (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: 'var(--color-danger)', fontSize: 11 }}
                          onClick={(e) => handleDeactivate(g.id, e)}
                        >
                          Désactiver
                        </button>
                      ) : (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: 'var(--color-success)', fontSize: 11 }}
                          onClick={(e) => handleReactivate(g.id, e)}
                        >
                          Réactiver
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
