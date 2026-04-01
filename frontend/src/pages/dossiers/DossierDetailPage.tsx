import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { dossiersService } from '@/services/dossiers.service'
import { clientsService } from '@/services/clients.service'
import type { Dossier, Client } from '@/types'
import { StatusBadge, UrgentBadge } from '@/components/ui/StatusBadge'
import { PageLoader } from '@/components/ui/Spinner'
import { formatDate, formatDateTime, isRetard, STATUT_LABELS } from '@/utils/statuts'
import { useAuth } from '@/features/auth/AuthContext'

interface InfoRowProps { label: string; value: React.ReactNode }
function InfoRow({ label, value }: InfoRowProps) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--color-border-light)' }}>
      <span style={{ width: 180, flexShrink: 0, fontSize: 12, color: 'var(--color-text-muted)', paddingTop: 1 }}>{label}</span>
      <span style={{ fontSize: 13 }}>{value ?? '—'}</span>
    </div>
  )
}

export function DossierDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [client, setClient] = useState<Client | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const canForceUrgent = user?.role === 'administratrice' || user?.role === 'coordinatrice'

  useEffect(() => {
    if (!id) return
    dossiersService.get(id)
      .then(async (d) => {
        setDossier(d)
        const c = await clientsService.get(d.client_id)
        setClient(c)
      })
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false))
  }, [id])

  async function handleForceUrgent() {
    if (!id || !dossier) return
    const updated = await dossiersService.forceUrgent(id)
    setDossier(updated)
  }

  if (isLoading) return <PageLoader />
  if (error) return <div className="page"><div className="alert alert-error">{error}</div></div>
  if (!dossier) return null

  const retard = isRetard(dossier.date_limite) && !['archive', 'envoye', 'facture', 'paye_entrant', 'prestataires_payes'].includes(dossier.statut)

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/dossiers')} style={{ padding: '2px 0' }}>
              ← Dossiers
            </button>
          </div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {dossier.reference}
            <StatusBadge statut={dossier.statut} />
            <UrgentBadge estUrgent={dossier.est_urgent} estRetard={retard && !dossier.est_urgent} />
          </h1>
          {dossier.titre && <p className="page-subtitle">{dossier.titre}</p>}
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          {canForceUrgent && !dossier.est_urgent && (
            <button className="btn btn-secondary btn-sm" onClick={handleForceUrgent}>
              🚨 Forcer urgent
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Informations principales */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Informations</h2>
          </div>
          <div className="card-body" style={{ padding: '4px 20px' }}>
            <InfoRow label="Référence" value={<strong>{dossier.reference}</strong>} />
            <InfoRow label="Type d'instance" value={<span className="badge badge-gray">{dossier.type_instance}</span>} />
            <InfoRow label="Client" value={client?.nom ?? dossier.client_id} />
            <InfoRow label="Statut" value={<StatusBadge statut={dossier.statut} />} />
            <InfoRow label="Confidentialité" value={dossier.niveau_confidentialite} />
            <InfoRow label="Date de séance" value={formatDate(dossier.date_seance)} />
            <InfoRow label="Réception audio" value={formatDateTime(dossier.date_reception_audio)} />
            <InfoRow
              label="Date limite"
              value={
                <span style={retard ? { color: 'var(--color-danger)', fontWeight: 600 } : {}}>
                  {formatDate(dossier.date_limite)}
                  {retard && ' ⚠️'}
                </span>
              }
            />
            <InfoRow label="Envoi client" value={formatDateTime(dossier.date_envoi_client)} />
            <InfoRow label="Durée audio" value={dossier.duree_audio_minutes ? `${dossier.duree_audio_minutes} min` : null} />
            <InfoRow label="Pages finales" value={dossier.nombre_pages_final} />
          </div>
        </div>

        {/* Workflow */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Workflow</h2>
          </div>
          <div className="card-body">
            <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 12 }}>
              Statut actuel : <strong style={{ color: 'var(--color-text)' }}>{STATUT_LABELS[dossier.statut]}</strong>
            </div>

            {/* Critères tarifaires */}
            {dossier.criteres_tarif && (
              <div style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: '10px 12px', marginBottom: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 6 }}>
                  Critères tarifaires
                </div>
                {Object.entries(dossier.criteres_tarif).map(([k, v]) => (
                  <div key={k} style={{ fontSize: 12, display: 'flex', gap: 6 }}>
                    <span style={{ color: 'var(--color-text-muted)', width: 160 }}>{k}</span>
                    <span>{String(v)}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Calcul tarifaire */}
            {dossier.calcul_tarifaire_id ? (
              <div className="badge badge-green" style={{ fontSize: 12 }}>
                ✓ Calcul tarifaire disponible
              </div>
            ) : (
              <div className="badge badge-gray" style={{ fontSize: 12 }}>
                Calcul tarifaire non encore généré
              </div>
            )}
          </div>
        </div>
      </div>

      {dossier.notes_internes && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <h2 className="card-title">Notes internes</h2>
            <span className="badge badge-orange">Confidentiel</span>
          </div>
          <div className="card-body">
            <p style={{ margin: 0, fontSize: 13, whiteSpace: 'pre-wrap' }}>{dossier.notes_internes}</p>
          </div>
        </div>
      )}
    </div>
  )
}
