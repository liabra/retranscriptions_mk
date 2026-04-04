import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { affectationsService } from '@/services/affectations.service'
import type { AffectationWithDossier } from '@/types'
import { PageLoader } from '@/components/ui/Spinner'
import { formatDate, STATUT_LABELS, STATUT_COLOR } from '@/utils/statuts'

const ROLE_LABELS: Record<string, string> = {
  retranscripteur: 'Retranscription',
  correcteur: 'Correction',
}

const STATUT_AFF_LABELS: Record<string, string> = {
  en_cours: 'En cours',
  livre: 'Livré',
  valide: 'Validé',
  rejete: 'Rejeté',
}

function ActionButton({ aff, onUpdate }: { aff: AffectationWithDossier; onUpdate: (updated: AffectationWithDossier) => void }) {
  const [loading, setLoading] = useState(false)

  async function deliver() {
    if (!confirm('Confirmer la livraison de votre travail sur ce dossier ?')) return
    setLoading(true)
    try {
      const updated = await affectationsService.update(aff.id, { statut: 'livre' })
      onUpdate({ ...aff, ...updated })
    } finally {
      setLoading(false)
    }
  }

  if (aff.statut === 'livre' || aff.statut === 'valide') {
    return (
      <span className="badge badge-green" style={{ fontSize: 11 }}>
        {STATUT_AFF_LABELS[aff.statut]}
      </span>
    )
  }

  if (aff.statut === 'en_cours') {
    return (
      <button className="btn btn-primary btn-sm" onClick={deliver} disabled={loading}>
        {loading ? '…' : 'J\'ai terminé'}
      </button>
    )
  }

  return null
}

export function MesDossiersPage() {
  const navigate = useNavigate()
  const [affectations, setAffectations] = useState<AffectationWithDossier[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    affectationsService.mesAffectations()
      .then(setAffectations)
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false))
  }, [])

  function handleUpdate(updated: AffectationWithDossier) {
    setAffectations((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
  }

  if (isLoading) return <PageLoader />

  const enCours = affectations.filter((a) => a.statut === 'en_cours')
  const livrees = affectations.filter((a) => a.statut !== 'en_cours' && a.statut !== 'rejete')

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Mes missions</h1>
          <p className="page-subtitle">Dossiers qui vous sont affectés</p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {affectations.length === 0 ? (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-muted)' }}>
            Aucune mission en cours.
          </div>
        </div>
      ) : (
        <>
          {enCours.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header">
                <h2 className="card-title">En cours ({enCours.length})</h2>
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                      {['Dossier', 'Statut dossier', 'Mission', 'Date limite', 'Action'].map((h) => (
                        <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600, fontSize: 11, color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {enCours.map((a) => (
                      <tr
                        key={a.id}
                        style={{ borderBottom: '1px solid var(--color-border-light)', cursor: 'pointer' }}
                        onClick={() => navigate(`/dossiers/${a.dossier.id}`)}
                      >
                        <td style={{ padding: '10px 12px' }}>
                          <strong>{a.dossier.reference}</strong>
                          {a.dossier.titre && <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{a.dossier.titre}</div>}
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <span className={`badge ${STATUT_COLOR[a.dossier.statut]}`} style={{ fontSize: 11 }}>
                            {STATUT_LABELS[a.dossier.statut]}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <span className="badge badge-blue" style={{ fontSize: 11 }}>{ROLE_LABELS[a.type_role]}</span>
                        </td>
                        <td style={{ padding: '10px 12px', color: a.date_limite_rendu && new Date(a.date_limite_rendu) < new Date() ? 'var(--color-danger)' : undefined }}>
                          {formatDate(a.date_limite_rendu)}
                        </td>
                        <td style={{ padding: '10px 12px' }} onClick={(e) => e.stopPropagation()}>
                          <ActionButton aff={a} onUpdate={handleUpdate} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {livrees.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h2 className="card-title" style={{ color: 'var(--color-text-muted)' }}>Terminées ({livrees.length})</h2>
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                      {['Dossier', 'Mission', 'Livré le', 'Statut'].map((h) => (
                        <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600, fontSize: 11, color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {livrees.map((a) => (
                      <tr
                        key={a.id}
                        style={{ borderBottom: '1px solid var(--color-border-light)', cursor: 'pointer', opacity: 0.7 }}
                        onClick={() => navigate(`/dossiers/${a.dossier.id}`)}
                      >
                        <td style={{ padding: '8px 12px' }}>
                          <strong>{a.dossier.reference}</strong>
                          {a.dossier.titre && <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{a.dossier.titre}</div>}
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          <span className="badge badge-blue" style={{ fontSize: 11 }}>{ROLE_LABELS[a.type_role]}</span>
                        </td>
                        <td style={{ padding: '8px 12px' }}>{formatDate(a.date_rendu_effectif ?? a.date_attribution)}</td>
                        <td style={{ padding: '8px 12px' }}>
                          <span className="badge badge-green" style={{ fontSize: 11 }}>{STATUT_AFF_LABELS[a.statut] ?? a.statut}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
