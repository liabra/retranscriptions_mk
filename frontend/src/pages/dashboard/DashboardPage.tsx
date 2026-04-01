import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { dossiersService } from '@/services/dossiers.service'
import type { DossierListItem } from '@/types'
import { useAuth } from '@/features/auth/AuthContext'
import { StatusBadge, UrgentBadge } from '@/components/ui/StatusBadge'
import { PageLoader } from '@/components/ui/Spinner'
import { formatDate, isRetard } from '@/utils/statuts'

interface Stats {
  enCours: number
  urgents: number
  enRetard: number
  aValider: number
}

export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [dossiers, setDossiers] = useState<DossierListItem[]>([])
  const [stats, setStats] = useState<Stats>({ enCours: 0, urgents: 0, enRetard: 0, aValider: 0 })
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    dossiersService.list({ limit: 100 })
      .then((data) => {
        setDossiers(data)
        setStats({
          enCours: data.filter((d) => !['archive', 'bloque'].includes(d.statut)).length,
          urgents: data.filter((d) => d.est_urgent).length,
          enRetard: data.filter((d) => isRetard(d.date_limite) && d.statut !== 'archive').length,
          aValider: data.filter((d) => d.statut === 'a_valider').length,
        })
      })
      .catch(console.error)
      .finally(() => setIsLoading(false))
  }, [])

  const recents = dossiers
    .filter((d) => d.statut !== 'archive')
    .sort((a, b) => {
      if (a.est_urgent !== b.est_urgent) return a.est_urgent ? -1 : 1
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })
    .slice(0, 10)

  if (isLoading) return <PageLoader />

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Bonjour, {user?.nom}</h1>
        <p className="page-subtitle">Vue d'ensemble des dossiers en cours</p>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-value">{stats.enCours}</div>
          <div className="stat-label">Dossiers en cours</div>
        </div>
        <div className={`stat-card${stats.urgents > 0 ? ' stat-urgent' : ''}`}>
          <div className="stat-value">{stats.urgents}</div>
          <div className="stat-label">Urgents</div>
        </div>
        <div className={`stat-card${stats.enRetard > 0 ? ' stat-retard' : ''}`}>
          <div className="stat-value">{stats.enRetard}</div>
          <div className="stat-label">En retard</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.aValider}</div>
          <div className="stat-label">À valider</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Dossiers prioritaires</h2>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/dossiers')}>
            Voir tous
          </button>
        </div>

        {recents.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-text">Aucun dossier en cours</div>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Référence</th>
                  <th>Type</th>
                  <th>Statut</th>
                  <th>Priorité</th>
                  <th>Date limite</th>
                </tr>
              </thead>
              <tbody>
                {recents.map((d) => (
                  <tr
                    key={d.id}
                    className={d.est_urgent ? 'row-urgent' : ''}
                    onClick={() => navigate(`/dossiers/${d.id}`)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <strong>{d.reference}</strong>
                      {d.titre && <div className="td-muted" style={{ fontSize: 11 }}>{d.titre}</div>}
                    </td>
                    <td className="td-muted">{d.type_instance}</td>
                    <td><StatusBadge statut={d.statut} /></td>
                    <td>
                      <UrgentBadge
                        estUrgent={d.est_urgent}
                        estRetard={isRetard(d.date_limite) && !d.est_urgent}
                      />
                    </td>
                    <td className="td-muted">{formatDate(d.date_limite)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
