import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { affectationsService } from '@/services/affectations.service'
import { uploadService } from '@/services/upload.service'
import { getApiErrorMessage } from '@/services/api'
import type { AffectationWithDossier, FichierDossier } from '@/types'
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

const PRESTA_ACCEPT = '.doc,.docx,.pdf,.odt,.txt'

function UploadZone({ dossierId, onUploaded }: { dossierId: string; onUploaded: (f: FichierDossier) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [commentaire, setCommentaire] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function handleFile(file: File) {
    setError('')
    setSuccess('')
    setUploading(true)
    try {
      const f = await uploadService.uploadFichier(dossierId, file, commentaire)
      onUploaded(f)
      setCommentaire('')
      setSuccess(`"${file.name}" déposé avec succès.`)
      setTimeout(() => setSuccess(''), 4000)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Commentaire (optionnel)"
          value={commentaire}
          onChange={(e) => setCommentaire(e.target.value)}
          style={{ fontSize: 12, padding: '4px 8px', border: '1px solid var(--color-border)', borderRadius: 4, flex: 1, minWidth: 140 }}
        />
        <button
          className="btn btn-sm"
          style={{ background: 'var(--color-border)', color: 'var(--color-text)' }}
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? 'Envoi…' : '📎 Déposer un fichier'}
        </button>
        <input ref={inputRef} type="file" accept={PRESTA_ACCEPT} style={{ display: 'none' }} onChange={handleChange} />
      </div>
      {error && <div style={{ fontSize: 11, color: 'var(--color-danger)', marginTop: 4 }}>{error}</div>}
      {success && <div style={{ fontSize: 11, color: 'var(--color-success)', marginTop: 4 }}>{success}</div>}
      <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 2 }}>Formats : .doc, .docx, .pdf, .odt, .txt</div>
    </div>
  )
}

function DepotsFichiers({ dossierId }: { dossierId: string }) {
  const [fichiers, setFichiers] = useState<FichierDossier[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (open && fichiers.length === 0) {
      uploadService.listFichiers(dossierId).then(setFichiers).catch(() => {})
    }
  }, [open, dossierId])

  return (
    <div style={{ marginTop: 6 }}>
      <button
        className="btn btn-ghost btn-sm"
        style={{ fontSize: 11, padding: '2px 6px' }}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? '▲ Masquer les dépôts' : `▼ Dépôts (${fichiers.length || '…'})`}
      </button>
      {open && (
        <div style={{ marginTop: 6, paddingLeft: 8, borderLeft: '2px solid var(--color-border-light)' }}>
          {fichiers.length === 0 ? (
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Aucun fichier déposé.</div>
          ) : (
            fichiers.map((f) => (
              <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, fontSize: 12 }}>
                <span>📄 {f.nom_fichier}</span>
                <span style={{ color: 'var(--color-text-muted)', fontSize: 10 }}>v{f.version}</span>
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: 10, padding: '1px 6px' }}
                  onClick={() => uploadService.downloadFichier(f.id, f.nom_fichier)}
                >
                  ↓ Télécharger
                </button>
              </div>
            ))
          )}
          <UploadZone dossierId={dossierId} onUploaded={(f) => setFichiers((prev) => [f, ...prev])} />
        </div>
      )}
    </div>
  )
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
                      <tr key={a.id} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                        <td style={{ padding: '10px 12px' }}>
                          <strong
                            style={{ cursor: 'pointer', color: 'var(--color-primary)' }}
                            onClick={() => navigate(`/dossiers/${a.dossier.id}`)}
                          >
                            {a.dossier.reference}
                          </strong>
                          {a.dossier.titre && <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{a.dossier.titre}</div>}
                          <DepotsFichiers dossierId={a.dossier.id} />
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
                        <td style={{ padding: '10px 12px' }}>
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
