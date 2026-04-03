import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { missionsService } from '@/services/missions.service'
import type { Mission } from '@/types'
import { PageLoader } from '@/components/ui/Spinner'
import { StatusBadge, UrgentBadge } from '@/components/ui/StatusBadge'
import { formatDate, isRetard } from '@/utils/statuts'

const STATUT_AFF_LABELS: Record<string, string> = {
  en_attente: 'En attente',
  en_cours: 'En cours',
  livre: 'Livré',
  valide: 'Validé',
  rejete: 'Rejeté',
}

const STATUT_AFF_BADGE: Record<string, string> = {
  en_attente: 'badge-yellow',
  en_cours: 'badge-blue',
  livre: 'badge-green',
  valide: 'badge-green',
  rejete: 'badge-red',
}

export function MissionsPage() {
  const navigate = useNavigate()
  const [missions, setMissions] = useState<Mission[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [delivering, setDelivering] = useState<string | null>(null)

  useEffect(() => {
    missionsService
      .list()
      .then(setMissions)
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false))
  }, [])

  async function handleLivrer(mission: Mission) {
    if (!mission.affectation_id) return
    if (!confirm('Confirmer la livraison de cette mission ?')) return
    setDelivering(mission.affectation_id)
    try {
      await missionsService.livrer(mission.affectation_id)
      setMissions((prev) =>
        prev.map((m) =>
          m.affectation_id === mission.affectation_id
            ? { ...m, statut_affectation: 'livre' as const }
            : m,
        ),
      )
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(detail ?? 'Erreur lors de la livraison')
    } finally {
      setDelivering(null)
    }
  }

  if (isLoading) return <PageLoader />

  const actives = missions.filter(
    (m) => m.statut_affectation !== 'valide' && m.statut_affectation !== 'rejete',
  )
  const terminees = missions.filter(
    (m) => m.statut_affectation === 'valide' || m.statut_affectation === 'rejete',
  )

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Mes missions</h1>
          <p className="page-subtitle">
            {actives.length} active{actives.length !== 1 ? 's' : ''}
            {terminees.length > 0 && ` · ${terminees.length} terminée${terminees.length !== 1 ? 's' : ''}`}
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {missions.length === 0 && !error ? (
        <div className="card">
          <div
            className="card-body"
            style={{
              textAlign: 'center',
              color: 'var(--color-text-muted)',
              padding: 40,
              fontSize: 14,
            }}
          >
            Aucune mission attribuée pour le moment
          </div>
        </div>
      ) : (
        <>
          {actives.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {actives.map((m) => {
                const retard = isRetard(m.date_limite_rendu)
                const canDeliver =
                  m.statut_affectation === 'en_attente' || m.statut_affectation === 'en_cours'
                return (
                  <div key={m.id} className="card">
                    <div className="card-body">
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          gap: 12,
                        }}
                      >
                        <div style={{ flex: 1 }}>
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              marginBottom: 6,
                              flexWrap: 'wrap',
                            }}
                          >
                            <strong style={{ fontSize: 15 }}>{m.reference}</strong>
                            <StatusBadge statut={m.statut} />
                            <UrgentBadge
                              estUrgent={m.est_urgent}
                              estRetard={retard && !m.est_urgent}
                            />
                            {m.role && (
                              <span
                                className="badge badge-blue"
                                style={{ textTransform: 'capitalize' }}
                              >
                                {m.role}
                              </span>
                            )}
                            {m.statut_affectation && (
                              <span
                                className={`badge ${STATUT_AFF_BADGE[m.statut_affectation] ?? 'badge-gray'}`}
                              >
                                {STATUT_AFF_LABELS[m.statut_affectation] ?? m.statut_affectation}
                              </span>
                            )}
                          </div>
                          {m.titre && (
                            <p
                              style={{
                                margin: '0 0 6px',
                                fontSize: 13,
                                color: 'var(--color-text-muted)',
                              }}
                            >
                              {m.titre}
                            </p>
                          )}
                          <div
                            style={{
                              display: 'flex',
                              gap: 16,
                              fontSize: 12,
                              color: 'var(--color-text-muted)',
                              flexWrap: 'wrap',
                            }}
                          >
                            <span>Type : {m.type_instance}</span>
                            {m.date_limite_rendu && (
                              <span
                                style={
                                  retard
                                    ? { color: 'var(--color-danger)', fontWeight: 600 }
                                    : {}
                                }
                              >
                                Rendu attendu : {formatDate(m.date_limite_rendu)}
                                {retard ? ' ⚠️' : ''}
                              </span>
                            )}
                            {m.date_limite && (
                              <span>Date limite dossier : {formatDate(m.date_limite)}</span>
                            )}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => navigate(`/dossiers/${m.id}`)}
                          >
                            Voir le dossier
                          </button>
                          {canDeliver && (
                            <button
                              className="btn btn-primary btn-sm"
                              disabled={delivering === m.affectation_id}
                              onClick={() => handleLivrer(m)}
                            >
                              {delivering === m.affectation_id ? '...' : 'Déclarer livraison'}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {terminees.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  color: 'var(--color-text-muted)',
                  marginBottom: 8,
                  padding: '0 2px',
                }}
              >
                Missions terminées
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {terminees.map((m) => (
                  <div
                    key={m.id}
                    className="card"
                    style={{ opacity: 0.65, cursor: 'pointer' }}
                    onClick={() => navigate(`/dossiers/${m.id}`)}
                  >
                    <div className="card-body" style={{ padding: '10px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 13, fontWeight: 500 }}>{m.reference}</span>
                        {m.role && (
                          <span
                            className="badge badge-gray"
                            style={{ textTransform: 'capitalize' }}
                          >
                            {m.role}
                          </span>
                        )}
                        {m.statut_affectation && (
                          <span
                            className={`badge ${STATUT_AFF_BADGE[m.statut_affectation] ?? 'badge-gray'}`}
                          >
                            {STATUT_AFF_LABELS[m.statut_affectation] ?? m.statut_affectation}
                          </span>
                        )}
                        {m.titre && (
                          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                            {m.titre}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
