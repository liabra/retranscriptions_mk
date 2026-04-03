import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { grillesService } from '@/services/grilles.service'
import type { GrilleTarifaire, RegleTarifaire, RegleCreate, TypeRegle, ConditionType, ModeCalcul } from '@/types'
import { PageLoader } from '@/components/ui/Spinner'

const TYPE_REGLE_LABELS: Record<TypeRegle, string> = {
  base: 'Base',
  majoration: 'Majoration',
  remise: 'Remise',
  forfait: 'Forfait',
  plancher: 'Plancher',
  plafond: 'Plafond',
}

const MODE_CALCUL_LABELS: Record<ModeCalcul, string> = {
  par_page: '€/page',
  forfait_fixe: 'Forfait fixe',
  pourcentage_base: '% base',
  pourcentage_total: '% total',
  multiplicateur: 'Multiplicateur',
}

const CONDITION_LABELS: Record<ConditionType, string> = {
  toujours: 'Toujours',
  si_type_instance: 'Si type instance',
  si_urgence: 'Si urgent',
  si_snp: 'Si SNP',
  si_special: 'Si spécial',
  si_duree: 'Si durée',
  si_volume: 'Si volume',
  si_client: 'Si client',
  combinee: 'Combinée',
}

const TYPE_REGLE_BADGE: Record<TypeRegle, string> = {
  base: 'badge-blue',
  majoration: 'badge-orange',
  remise: 'badge-green',
  forfait: 'badge-blue',
  plancher: 'badge-yellow',
  plafond: 'badge-yellow',
}

const EMPTY_REGLE: RegleCreate = {
  libelle: '',
  type_regle: 'base',
  condition_type: 'toujours',
  mode_calcul: 'par_page',
  valeur: '0',
  priorite: 100,
}

export function GrilleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [grille, setGrille] = useState<(GrilleTarifaire & { regles: RegleTarifaire[] }) | null>(
    null,
  )
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [showRegleForm, setShowRegleForm] = useState(false)
  const [regleForm, setRegleForm] = useState<RegleCreate>(EMPTY_REGLE)
  const [savingRegle, setSavingRegle] = useState(false)
  const [regleError, setRegleError] = useState('')

  useEffect(() => {
    if (!id) return
    grillesService
      .get(id)
      .then(setGrille)
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false))
  }, [id])

  async function handleCreateRegle(e: React.FormEvent) {
    e.preventDefault()
    if (!id) return
    setRegleError('')
    setSavingRegle(true)
    try {
      const created = await grillesService.createRegle(id, regleForm)
      setGrille((prev) => (prev ? { ...prev, regles: [...prev.regles, created] } : prev))
      setShowRegleForm(false)
      setRegleForm(EMPTY_REGLE)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setRegleError(typeof detail === 'string' ? detail : 'Erreur')
    } finally {
      setSavingRegle(false)
    }
  }

  async function handleDeleteRegle(regleId: string) {
    if (!confirm('Désactiver cette règle ?')) return
    await grillesService.deleteRegle(regleId)
    setGrille((prev) =>
      prev
        ? { ...prev, regles: prev.regles.map((r) => (r.id === regleId ? { ...r, actif: false } : r)) }
        : prev,
    )
  }

  if (isLoading) return <PageLoader />
  if (error) return <div className="page"><div className="alert alert-error">{error}</div></div>
  if (!grille) return null

  const reglesActives = grille.regles.filter((r) => r.actif)
  const reglesInactives = grille.regles.filter((r) => !r.actif)

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => navigate('/grilles')}
            style={{ padding: '2px 0', marginBottom: 4 }}
          >
            ← Grilles
          </button>
          <h1 className="page-title">{grille.nom}</h1>
          <p className="page-subtitle">
            v{grille.version} · {grille.type} ·{' '}
            {grille.active ? (
              <span className="badge badge-green" style={{ fontSize: 11 }}>Active</span>
            ) : (
              <span className="badge badge-gray" style={{ fontSize: 11 }}>Inactive</span>
            )}
          </p>
        </div>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setShowRegleForm((v) => !v)}
        >
          {showRegleForm ? 'Annuler' : '+ Ajouter une règle'}
        </button>
      </div>

      {grille.description && (
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 16 }}>
          {grille.description}
        </p>
      )}

      {showRegleForm && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <h2 className="card-title">Nouvelle règle</h2>
          </div>
          <div className="card-body">
            <form onSubmit={handleCreateRegle}>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 10 }}>
                <div>
                  <label className="form-label">Libellé</label>
                  <input
                    className="form-input"
                    value={regleForm.libelle}
                    onChange={(e) => setRegleForm((f) => ({ ...f, libelle: e.target.value }))}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">Type</label>
                  <select
                    className="form-input"
                    value={regleForm.type_regle}
                    onChange={(e) =>
                      setRegleForm((f) => ({ ...f, type_regle: e.target.value as TypeRegle }))
                    }
                  >
                    {Object.entries(TYPE_REGLE_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="form-label">Condition</label>
                  <select
                    className="form-input"
                    value={regleForm.condition_type ?? 'toujours'}
                    onChange={(e) =>
                      setRegleForm((f) => ({
                        ...f,
                        condition_type: e.target.value as ConditionType,
                      }))
                    }
                  >
                    {Object.entries(CONDITION_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="form-label">Mode de calcul</label>
                  <select
                    className="form-input"
                    value={regleForm.mode_calcul}
                    onChange={(e) =>
                      setRegleForm((f) => ({ ...f, mode_calcul: e.target.value as ModeCalcul }))
                    }
                  >
                    {Object.entries(MODE_CALCUL_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="form-label">Valeur</label>
                  <input
                    className="form-input"
                    type="number"
                    step="0.0001"
                    value={regleForm.valeur}
                    onChange={(e) => setRegleForm((f) => ({ ...f, valeur: e.target.value }))}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">Unité</label>
                  <input
                    className="form-input"
                    placeholder="€/page"
                    value={regleForm.unite ?? ''}
                    onChange={(e) =>
                      setRegleForm((f) => ({ ...f, unite: e.target.value || undefined }))
                    }
                  />
                </div>
                <div>
                  <label className="form-label">Priorité</label>
                  <input
                    className="form-input"
                    type="number"
                    value={regleForm.priorite ?? 100}
                    onChange={(e) =>
                      setRegleForm((f) => ({ ...f, priorite: Number(e.target.value) }))
                    }
                  />
                </div>
                <div>
                  <label className="form-label">Plafond montant</label>
                  <input
                    className="form-input"
                    type="number"
                    step="0.01"
                    value={regleForm.plafond_montant ?? ''}
                    onChange={(e) =>
                      setRegleForm((f) => ({
                        ...f,
                        plafond_montant: e.target.value || undefined,
                      }))
                    }
                  />
                </div>
              </div>
              {regleError && (
                <div className="alert alert-error" style={{ marginTop: 8 }}>
                  {regleError}
                </div>
              )}
              <div style={{ marginTop: 10 }}>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={savingRegle}
                >
                  {savingRegle ? '...' : 'Ajouter'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Règles actives ({reglesActives.length})</h2>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {reglesActives.length === 0 ? (
            <div
              style={{
                padding: 24,
                textAlign: 'center',
                color: 'var(--color-text-muted)',
                fontSize: 14,
              }}
            >
              Aucune règle active
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  {['Prio', 'Libellé', 'Type', 'Condition', 'Mode', 'Valeur', ''].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: 'left',
                        padding: '8px 10px',
                        fontWeight: 600,
                        fontSize: 10,
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
                {[...reglesActives]
                  .sort((a, b) => a.priorite - b.priorite)
                  .map((r) => (
                    <tr
                      key={r.id}
                      style={{ borderBottom: '1px solid var(--color-border-light)' }}
                    >
                      <td style={{ padding: '8px 10px', color: 'var(--color-text-muted)' }}>
                        {r.priorite}
                      </td>
                      <td style={{ padding: '8px 10px', fontWeight: 500 }}>{r.libelle}</td>
                      <td style={{ padding: '8px 10px' }}>
                        <span className={`badge ${TYPE_REGLE_BADGE[r.type_regle]}`}>
                          {TYPE_REGLE_LABELS[r.type_regle]}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px' }}>{CONDITION_LABELS[r.condition_type]}</td>
                      <td style={{ padding: '8px 10px' }}>{MODE_CALCUL_LABELS[r.mode_calcul]}</td>
                      <td style={{ padding: '8px 10px' }}>
                        <strong>{r.valeur}</strong>
                        {r.unite && (
                          <span style={{ color: 'var(--color-text-muted)', marginLeft: 4 }}>
                            {r.unite}
                          </span>
                        )}
                        {r.plafond_montant && (
                          <span
                            style={{
                              color: 'var(--color-text-muted)',
                              marginLeft: 6,
                              fontSize: 11,
                            }}
                          >
                            (plafond: {r.plafond_montant}€)
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ fontSize: 11, color: 'var(--color-danger)' }}
                          onClick={() => handleDeleteRegle(r.id)}
                        >
                          Désactiver
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {reglesInactives.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-header">
            <h2 className="card-title" style={{ color: 'var(--color-text-muted)' }}>
              Règles désactivées ({reglesInactives.length})
            </h2>
          </div>
          <div className="card-body" style={{ padding: '8px 0' }}>
            {reglesInactives.map((r) => (
              <div
                key={r.id}
                style={{
                  padding: '6px 16px',
                  fontSize: 12,
                  color: 'var(--color-text-muted)',
                  opacity: 0.6,
                }}
              >
                {r.libelle} — {TYPE_REGLE_LABELS[r.type_regle]} — {r.valeur} {r.unite}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
