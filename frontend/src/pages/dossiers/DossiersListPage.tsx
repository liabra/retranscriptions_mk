import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { dossiersService } from '@/services/dossiers.service'
import { clientsService } from '@/services/clients.service'
import type { DossierListItem, Client, StatutDossier } from '@/types'
import { StatusBadge, UrgentBadge } from '@/components/ui/StatusBadge'
import { PageLoader } from '@/components/ui/Spinner'
import { formatDate, isRetard, STATUT_LABELS } from '@/utils/statuts'
import { useAuth } from '@/features/auth/AuthContext'

const STATUTS_FILTRABLES: StatutDossier[] = [
  'recu', 'en_qualification', 'estime', 'a_attribuer',
  'en_retranscription', 'a_corriger', 'en_correction',
  'en_mise_en_forme', 'calcul_en_cours', 'a_valider',
  'envoye', 'facture', 'paye_entrant', 'bloque',
]

export function DossiersListPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [dossiers, setDossiers] = useState<DossierListItem[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const [filterStatut, setFilterStatut] = useState<StatutDossier | ''>('')
  const [filterUrgent, setFilterUrgent] = useState(false)
  const [filterClient, setFilterClient] = useState('')

  const canCreate = user?.role === 'administratrice' || user?.role === 'coordinatrice'

  useEffect(() => {
    Promise.all([
      dossiersService.list({ statut: filterStatut || undefined, urgent_only: filterUrgent || undefined, client_id: filterClient || undefined }),
      clientsService.list(),
    ])
      .then(([d, c]) => { setDossiers(d); setClients(c) })
      .catch(console.error)
      .finally(() => setIsLoading(false))
  }, [filterStatut, filterUrgent, filterClient])

  const clientMap = Object.fromEntries(clients.map((c) => [c.id, c.nom]))

  if (isLoading) return <PageLoader />

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Dossiers</h1>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
            {dossiers.length} dossier{dossiers.length > 1 ? 's' : ''}
          </p>
        </div>
        {canCreate && (
          <button className="btn btn-primary" onClick={() => navigate('/dossiers/nouveau')}>
            + Nouveau dossier
          </button>
        )}
      </div>

      <div className="filter-row">
        <select
          className="filter-select"
          value={filterStatut}
          onChange={(e) => setFilterStatut(e.target.value as StatutDossier | '')}
        >
          <option value="">Tous les statuts</option>
          {STATUTS_FILTRABLES.map((s) => (
            <option key={s} value={s}>{STATUT_LABELS[s]}</option>
          ))}
        </select>

        <select
          className="filter-select"
          value={filterClient}
          onChange={(e) => setFilterClient(e.target.value)}
        >
          <option value="">Tous les clients</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>{c.nom}</option>
          ))}
        </select>

        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={filterUrgent}
            onChange={(e) => setFilterUrgent(e.target.checked)}
          />
          Urgents uniquement
        </label>
      </div>

      <div className="card">
        {dossiers.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-text">Aucun dossier trouvé</div>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Référence</th>
                  <th>Client</th>
                  <th>Type</th>
                  <th>Statut</th>
                  <th>Priorité</th>
                  <th>Date limite</th>
                  <th>Créé le</th>
                </tr>
              </thead>
              <tbody>
                {dossiers.map((d) => {
                  const retard = isRetard(d.date_limite) && !['archive', 'envoye', 'facture', 'paye_entrant', 'prestataires_payes'].includes(d.statut)
                  return (
                    <tr
                      key={d.id}
                      className={d.est_urgent ? 'row-urgent' : ''}
                      onClick={() => navigate(`/dossiers/${d.id}`)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <strong>{d.reference}</strong>
                        {d.titre && <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{d.titre}</div>}
                      </td>
                      <td className="td-muted">{clientMap[d.client_id] ?? '—'}</td>
                      <td><span className="badge badge-gray">{d.type_instance}</span></td>
                      <td><StatusBadge statut={d.statut} /></td>
                      <td><UrgentBadge estUrgent={d.est_urgent} estRetard={retard && !d.est_urgent} /></td>
                      <td className={retard ? '' : 'td-muted'} style={retard ? { color: 'var(--color-danger)', fontWeight: 600 } : {}}>
                        {formatDate(d.date_limite)}
                      </td>
                      <td className="td-muted">{formatDate(d.created_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
