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

// ── Icônes ───────────────────────────────────────────────────────────────────
function Icon({ path, size = 16 }: { path: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  )
}
const I_DOWNLOAD = 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4 M7 10l5 5 5-5 M12 15V3'
const I_UPLOAD = 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4 M17 8l-5-5-5 5 M12 3v12'
const I_AUDIO = 'M9 18V5l12-2v13 M9 13a3 3 0 11-6 0 3 3 0 016 0z M21 16a3 3 0 11-6 0 3 3 0 016 0z'
const I_OPEN = 'M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6 M15 3h6v6 M10 14L21 3'

// ── Échéance : libellé + couleur ─────────────────────────────────────────────
function echeance(dateStr: string | null): { texte: string; retard: boolean } {
  if (!dateStr) return { texte: 'Sans échéance', retard: false }
  const d = new Date(dateStr)
  const jours = Math.ceil((d.getTime() - Date.now()) / 86400000)
  if (jours < 0) return { texte: `En retard de ${Math.abs(jours)} j`, retard: true }
  if (jours === 0) return { texte: "Échéance aujourd'hui", retard: true }
  if (jours === 1) return { texte: 'Échéance demain', retard: false }
  return { texte: `${jours} jours restants`, retard: false }
}

// ── Fichiers du dossier (audio à télécharger + dépôts) ───────────────────────
function MissionFichiers({ dossierId }: { dossierId: string }) {
  const [fichiers, setFichiers] = useState<FichierDossier[]>([])
  const [chargement, setChargement] = useState(true)

  useEffect(() => {
    uploadService.listFichiers(dossierId)
      .then(setFichiers)
      .catch(() => {})
      .finally(() => setChargement(false))
  }, [dossierId])

  function ajouter(f: FichierDossier) {
    setFichiers((prev) => [f, ...prev])
  }

  const audio = fichiers.filter((f) => f.type_document === 'audio_brut')
  const autres = fichiers.filter((f) => f.type_document !== 'audio_brut')

  return (
    <div style={{ marginTop: 16 }}>
      {/* Audio source */}
      <div className="presta-block-title"><Icon path={I_AUDIO} size={15} /> Audio à retranscrire</div>
      {chargement ? (
        <div className="presta-muted">Chargement…</div>
      ) : audio.length === 0 ? (
        <div className="presta-muted">Aucun audio déposé pour le moment.</div>
      ) : (
        audio.map((f) => <FichierLigne key={f.id} f={f} />)
      )}

      {/* Dépôt de la retranscription */}
      <div className="presta-block-title" style={{ marginTop: 16 }}><Icon path={I_UPLOAD} size={15} /> Déposer ma retranscription</div>
      <DropZone dossierId={dossierId} onUploaded={ajouter} />

      {autres.length > 0 && (
        <div style={{ marginTop: 12 }}>
          {autres.map((f) => <FichierLigne key={f.id} f={f} depot />)}
        </div>
      )}
    </div>
  )
}

function FichierLigne({ f, depot = false }: { f: FichierDossier; depot?: boolean }) {
  const estLien = /^https?:\/\//.test(f.url_onedrive)
  return (
    <div className="presta-file">
      <span className="presta-file-name">
        {depot ? '↳ ' : ''}{f.nom_fichier}
        <span className="presta-file-ver">v{f.version}</span>
      </span>
      <span style={{ display: 'flex', gap: 6 }}>
        {estLien && (
          <a href={f.url_onedrive} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm">
            <Icon path={I_OPEN} size={14} /> Ouvrir
          </a>
        )}
        <button className="btn btn-secondary btn-sm" onClick={() => uploadService.downloadFichier(f.id, f.nom_fichier)}>
          <Icon path={I_DOWNLOAD} size={14} /> Télécharger
        </button>
      </span>
    </div>
  )
}

// ── Zone de dépôt (glisser-déposer) ──────────────────────────────────────────
function DropZone({ dossierId, onUploaded }: { dossierId: string; onUploaded: (f: FichierDossier) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [commentaire, setCommentaire] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState('')
  const [succes, setSucces] = useState('')
  const [survol, setSurvol] = useState(false)

  async function envoyer(file: File) {
    setErreur(''); setSucces(''); setEnvoi(true)
    try {
      const f = await uploadService.uploadFichier(dossierId, file, commentaire)
      onUploaded(f)
      setCommentaire('')
      setSucces(`« ${file.name} » déposé avec succès.`)
      setTimeout(() => setSucces(''), 4000)
    } catch (err) {
      setErreur(getApiErrorMessage(err))
    } finally {
      setEnvoi(false)
    }
  }

  function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) envoyer(file)
    e.target.value = ''
  }
  function onDrop(e: React.DragEvent) {
    e.preventDefault(); setSurvol(false)
    const file = e.dataTransfer.files?.[0]
    if (file) envoyer(file)
  }

  return (
    <div>
      <div
        className={`presta-dropzone${survol ? ' over' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setSurvol(true) }}
        onDragLeave={() => setSurvol(false)}
        onDrop={onDrop}
        role="button"
        tabIndex={0}
      >
        <Icon path={I_UPLOAD} size={22} />
        <div className="presta-dropzone-text">
          {envoi ? 'Envoi en cours…' : 'Glissez votre fichier ici, ou cliquez pour parcourir'}
        </div>
        <div className="presta-dropzone-sub">Formats acceptés : .doc, .docx, .pdf, .odt, .txt</div>
      </div>
      <input ref={inputRef} type="file" accept={PRESTA_ACCEPT} style={{ display: 'none' }} onChange={onChange} />
      <input
        type="text"
        className="form-input"
        style={{ marginTop: 8, fontSize: 13 }}
        placeholder="Commentaire pour cette livraison (optionnel)"
        value={commentaire}
        onChange={(e) => setCommentaire(e.target.value)}
      />
      {erreur && <div className="alert alert-error" style={{ marginTop: 8 }}>{erreur}</div>}
      {succes && <div className="alert alert-success" style={{ marginTop: 8 }}>{succes}</div>}
    </div>
  )
}

// ── Carte de mission ─────────────────────────────────────────────────────────
function MissionCard({ aff, onUpdate }: { aff: AffectationWithDossier; onUpdate: (a: AffectationWithDossier) => void }) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const ech = echeance(aff.date_limite_rendu)

  async function livrer() {
    if (!confirm('Confirmer la livraison de votre travail sur ce dossier ?')) return
    setLoading(true)
    try {
      const updated = await affectationsService.update(aff.id, { statut: 'livre' })
      onUpdate({ ...aff, ...updated })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card presta-card">
      <div className="presta-card-head">
        <div>
          <div className="presta-ref" onClick={() => navigate(`/dossiers/${aff.dossier.id}`)}>
            {aff.dossier.reference}
          </div>
          {aff.dossier.titre && <div className="presta-titre">{aff.dossier.titre}</div>}
          <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
            <span className="badge badge-blue">{ROLE_LABELS[aff.type_role] ?? aff.type_role}</span>
            <span className={`badge ${STATUT_COLOR[aff.dossier.statut]}`}>{STATUT_LABELS[aff.dossier.statut]}</span>
          </div>
        </div>
        <div className={`presta-echeance${ech.retard ? ' retard' : ''}`}>
          <div className="presta-echeance-label">À rendre</div>
          <div className="presta-echeance-date">{formatDate(aff.date_limite_rendu)}</div>
          <div className="presta-echeance-jours">{ech.texte}</div>
        </div>
      </div>

      <MissionFichiers dossierId={aff.dossier.id} />

      <div className="presta-card-foot">
        {aff.statut === 'en_cours' ? (
          <button className="btn btn-primary" onClick={livrer} disabled={loading}>
            {loading ? '…' : 'Marquer ma mission comme terminée'}
          </button>
        ) : (
          <span className="badge badge-green">{STATUT_AFF_LABELS[aff.statut] ?? aff.statut}</span>
        )}
      </div>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────
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
          <p className="page-subtitle">Les dossiers qui vous sont confiés</p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {affectations.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon" aria-hidden="true"><Icon path={I_AUDIO} size={38} /></div>
            <div className="empty-state-text">Aucune mission en cours pour l'instant.</div>
          </div>
        </div>
      ) : (
        <>
          {enCours.length > 0 && (
            <>
              <div className="presta-section-title">En cours · {enCours.length}</div>
              {enCours.map((a) => <MissionCard key={a.id} aff={a} onUpdate={handleUpdate} />)}
            </>
          )}

          {livrees.length > 0 && (
            <>
              <div className="presta-section-title" style={{ marginTop: 24, color: 'var(--color-text-muted)' }}>
                Terminées · {livrees.length}
              </div>
              <div className="card">
                <div className="card-body" style={{ padding: 0 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <tbody>
                      {livrees.map((a) => (
                        <tr
                          key={a.id}
                          style={{ borderBottom: '1px solid var(--color-border-light)', cursor: 'pointer' }}
                          onClick={() => navigate(`/dossiers/${a.dossier.id}`)}
                        >
                          <td style={{ padding: '12px 16px' }}>
                            <strong>{a.dossier.reference}</strong>
                            {a.dossier.titre && <div className="presta-muted">{a.dossier.titre}</div>}
                          </td>
                          <td style={{ padding: '12px 16px' }}>
                            <span className="badge badge-blue">{ROLE_LABELS[a.type_role] ?? a.type_role}</span>
                          </td>
                          <td style={{ padding: '12px 16px' }} className="presta-muted">
                            {formatDate(a.date_rendu_effectif ?? a.date_attribution)}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                            <span className="badge badge-green">{STATUT_AFF_LABELS[a.statut] ?? a.statut}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
