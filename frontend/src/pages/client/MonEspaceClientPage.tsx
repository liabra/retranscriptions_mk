/**
 * Espace client — dépôt de fichiers audio sur les dossiers associés au client connecté.
 * Le rôle CLIENT voit uniquement ses dossiers (filtrés côté backend par email_contact).
 */
import { useEffect, useRef, useState } from 'react'
import { dossiersService } from '@/services/dossiers.service'
import { uploadService } from '@/services/upload.service'
import { getApiErrorMessage } from '@/services/api'
import type { DossierListItem, FichierDossier } from '@/types'
import { PageLoader } from '@/components/ui/Spinner'
import { formatDate, STATUT_LABELS, STATUT_COLOR } from '@/utils/statuts'

const AUDIO_ACCEPT = '.mp3,.wav,.m4a,.mp4'
const AUDIO_FORMATS = '.mp3, .wav, .m4a, .mp4'

// ── Composant dépôt audio par dossier ────────────────────────────────────────

function AudioDepotCard({ dossier }: { dossier: DossierListItem }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [fichiers, setFichiers] = useState<FichierDossier[]>([])
  const [loadingFichiers, setLoadingFichiers] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [commentaire, setCommentaire] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    uploadService
      .listFichiers(dossier.id)
      .then(setFichiers)
      .catch(() => setFichiers([]))
      .finally(() => setLoadingFichiers(false))
  }, [dossier.id])

  async function handleFile(file: File) {
    setError('')
    setSuccess('')
    setUploading(true)
    try {
      const f = await uploadService.uploadFichier(dossier.id, file, commentaire)
      setFichiers((prev) => [f, ...prev])
      setCommentaire('')
      setSuccess(`"${file.name}" envoyé avec succès. L'administratrice a été notifiée.`)
      setTimeout(() => setSuccess(''), 6000)
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
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h3 className="card-title" style={{ margin: 0 }}>{dossier.reference}</h3>
          {dossier.titre && (
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{dossier.titre}</div>
          )}
        </div>
        <span className={`badge ${STATUT_COLOR[dossier.statut]}`} style={{ fontSize: 11 }}>
          {STATUT_LABELS[dossier.statut]}
        </span>
      </div>

      <div className="card-body">
        {/* Zone de dépôt */}
        <div
          style={{
            border: '2px dashed var(--color-border)',
            borderRadius: 8,
            padding: '20px 16px',
            textAlign: 'center',
            background: 'var(--color-bg-subtle)',
          }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            const file = e.dataTransfer.files[0]
            if (file) handleFile(file)
          }}
        >
          <div style={{ fontSize: 28, marginBottom: 8 }}>🎙</div>
          <div style={{ fontSize: 13, marginBottom: 8, color: 'var(--color-text-muted)' }}>
            Glissez votre fichier audio ici ou cliquez sur le bouton
          </div>
          <input
            type="text"
            placeholder="Message pour l'administratrice (optionnel)"
            value={commentaire}
            onChange={(e) => setCommentaire(e.target.value)}
            style={{
              fontSize: 12,
              padding: '6px 10px',
              border: '1px solid var(--color-border)',
              borderRadius: 4,
              width: '100%',
              maxWidth: 360,
              marginBottom: 10,
              boxSizing: 'border-box',
            }}
          />
          <div>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? 'Envoi en cours…' : '📎 Choisir un fichier audio'}
            </button>
            <input
              ref={inputRef}
              type="file"
              accept={AUDIO_ACCEPT}
              style={{ display: 'none' }}
              onChange={handleChange}
            />
          </div>
          <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 8 }}>
            Formats acceptés : {AUDIO_FORMATS}
          </div>
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginTop: 10, fontSize: 12 }}>{error}</div>
        )}
        {success && (
          <div className="alert alert-success" style={{ marginTop: 10, fontSize: 12 }}>{success}</div>
        )}

        {/* Liste des dépôts existants */}
        {!loadingFichiers && fichiers.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              Fichiers déposés ({fichiers.length})
            </div>
            {fichiers.map((f) => (
              <div
                key={f.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '6px 0',
                  borderBottom: '1px solid var(--color-border-light)',
                  fontSize: 13,
                }}
              >
                <span style={{ flex: 1 }}>🎵 {f.nom_fichier}</span>
                <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{formatDate(f.created_at)}</span>
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: 11 }}
                  onClick={() => uploadService.downloadFichier(f.id, f.nom_fichier)}
                >
                  ↓
                </button>
              </div>
            ))}
          </div>
        )}

        {dossier.date_limite && (
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--color-text-muted)' }}>
            Date limite : <strong>{formatDate(dossier.date_limite)}</strong>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Page principale ───────────────────────────────────────────────────────────

export function MonEspaceClientPage() {
  const [dossiers, setDossiers] = useState<DossierListItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    dossiersService
      .list({ limit: 50 })
      .then(setDossiers)
      .catch((e) => setError(getApiErrorMessage(e)))
      .finally(() => setIsLoading(false))
  }, [])

  if (isLoading) return <PageLoader />

  // Dossiers actifs (non archivés)
  const actifs = dossiers.filter((d) => d.statut !== 'archive' && d.statut !== 'prestataires_payes')
  const archives = dossiers.filter((d) => d.statut === 'archive' || d.statut === 'prestataires_payes')

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Mon espace</h1>
          <p className="page-subtitle">Déposez vos fichiers audio pour vos dossiers de retranscription</p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {dossiers.length === 0 && !error && (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-muted)' }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
            <div>Aucun dossier en cours.</div>
            <div style={{ fontSize: 12, marginTop: 8 }}>
              Contactez votre administratrice pour créer un dossier.
            </div>
          </div>
        </div>
      )}

      {actifs.map((d) => (
        <AudioDepotCard key={d.id} dossier={d} />
      ))}

      {archives.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 14, color: 'var(--color-text-muted)', marginBottom: 12 }}>
            Dossiers terminés ({archives.length})
          </h2>
          {archives.map((d) => (
            <div
              key={d.id}
              className="card"
              style={{ marginBottom: 8, opacity: 0.6 }}
            >
              <div className="card-body" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px' }}>
                <div>
                  <strong>{d.reference}</strong>
                  {d.titre && <span style={{ fontSize: 12, color: 'var(--color-text-muted)', marginLeft: 8 }}>{d.titre}</span>}
                </div>
                <span className={`badge ${STATUT_COLOR[d.statut]}`} style={{ fontSize: 11 }}>
                  {STATUT_LABELS[d.statut]}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
