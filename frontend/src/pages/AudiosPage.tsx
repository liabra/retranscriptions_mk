import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AudioLines, CheckCircle2, Download, EyeOff, Link2, RefreshCw, RotateCcw, Upload } from 'lucide-react'
import { api, type Audio } from '@/lib/api'
import { downloadFile } from '@/services/api'
import { fDateTime, fDuree, fSize } from '@/lib/format'
import { Alert, Empty, ErrorBox, Field, FileDrop, Modal, PageLoader, Pill, Tabs } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'
import { NouveauDossier } from '@/pages/DossiersPage'

const ORIGINES: Record<string, string> = {
  lien_manuel: 'Lien OneDrive', fichier: 'Fichier déposé', detection_graph: 'Détecté dans OneDrive', depot_client: 'Déposé par le client',
}

export function AudiosPage() {
  const [vue, setVue] = useState<'a_traiter' | 'associe' | 'ignore'>('a_traiter')
  const list = useLoad(() => api.audios(vue), [vue])
  const synchro = useLoad(() => api.synchro())
  const [ajout, setAjout] = useState<'lien' | 'fichier' | null>(null)
  const [mission, setMission] = useState<Audio | null>(null)
  const action = useAction()
  const navigate = useNavigate()

  const s = synchro.data as Record<string, string | number | boolean | null> | null

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Audios reçus</h1>
          <p>Les audios restent dans le OneDrive de l'association. La plateforme sert d'intermédiaire sécurisé.</p>
        </div>
        <div className="row">
          <button className="btn btn-secondary" onClick={() => setAjout('lien')}><Link2 size={17} />Ajouter un lien OneDrive</button>
          <button className="btn btn-primary" onClick={() => setAjout('fichier')}><Upload size={17} />Déposer un fichier</button>
        </div>
      </div>

      {s && (
        <div className="card card-pad row" style={{ justifyContent: 'space-between' }}>
          <div className="row">
            <span className={`kpi-icon tone-${s.detection_automatique_active ? 'green' : 'gray'}`}><RefreshCw size={17} /></span>
            <div>
              <div style={{ fontWeight: 600 }}>Détection automatique OneDrive {s.detection_automatique_active ? 'active' : 'inactive'}</div>
              <div className="small muted">
                {!s.onedrive_configure ? 'OneDrive n’est pas encore relié à la plateforme (configuration Microsoft à réaliser). L’ajout manuel fonctionne normalement.'
                  : `Dossier surveillé : ${s.dossier_surveille} · dernière vérification ${fDateTime(s.derniere_execution as string)}`}
                {s.derniere_erreur ? ` · Dernière erreur : ${s.derniere_erreur}` : ''}
              </div>
            </div>
          </div>
          {s.onedrive_configure && (
            <button className="btn btn-secondary btn-sm" disabled={action.busy}
              onClick={() => action.run(async () => { await api.lancerSynchro(); synchro.reload(); list.reload(); toast('Vérification terminée') })}>
              <RefreshCw size={15} />Vérifier maintenant
            </button>
          )}
        </div>
      )}

      <ErrorBox error={action.error ?? list.error} />
      <Tabs value={vue} onChange={setVue} items={[
        { key: 'a_traiter', label: 'À traiter' }, { key: 'associe', label: 'Associés à un dossier' }, { key: 'ignore', label: 'Ignorés' },
      ]} />

      <div className="card">
        {list.loading && !list.data ? <PageLoader /> : !list.data?.length ? (
          <Empty icon={<AudioLines size={24} />} title={vue === 'a_traiter' ? 'Aucun nouvel audio' : 'Rien ici'}>
            {vue === 'a_traiter' ? 'Ajoutez un lien OneDrive ou déposez un fichier pour créer une mission.' : ''}
          </Empty>
        ) : (
          <div className="list">
            {list.data.map((a) => (
              <div key={a.id} className="list-item">
                <span className="kpi-icon tone-primary"><AudioLines size={18} /></span>
                <div className="list-main">
                  <div className="list-title ellipsis">{a.nom_fichier}</div>
                  <div className="small muted">
                    {ORIGINES[a.origine] ?? a.origine} · {fDateTime(a.created_at)}{a.client_nom ? ` · ${a.client_nom}` : ''}
                    {a.taille_octets ? ` · ${fSize(a.taille_octets)}` : ''}{a.duree_minutes ? ` · ${fDuree(a.duree_minutes)}` : ''}
                  </div>
                  {!a.disponible && a.message_verification && <div className="small" style={{ color: 'var(--amber)' }}>{a.message_verification}</div>}
                </div>
                <Pill tone={a.disponible ? 'green' : 'amber'} dot>{a.disponible ? 'Vérifié' : 'Non vérifié'}</Pill>
                <div className="row" style={{ gap: 6 }}>
                  {a.disponible && <button className="btn btn-ghost btn-sm" aria-label="Télécharger"
                    onClick={() => action.run(() => downloadFile(`/audios/${a.id}/fichier`, a.nom_fichier))}><Download size={16} /></button>}
                  {!a.disponible && <button className="btn btn-ghost btn-sm" onClick={() => action.run(async () => { await api.verifierAudio(a.id); list.reload() })}>Vérifier</button>}
                  {vue === 'a_traiter' && <>
                    <button className="btn btn-ghost btn-sm" title="Ignorer" aria-label="Ignorer" onClick={() => action.run(async () => { await api.ignorerAudio(a.id); list.reload() })}><EyeOff size={16} /></button>
                    <button className="btn btn-primary btn-sm" onClick={() => setMission(a)}><CheckCircle2 size={16} />Créer la mission</button>
                  </>}
                  {vue === 'ignore' && <button className="btn btn-ghost btn-sm" onClick={() => action.run(async () => { await api.retablirAudio(a.id); list.reload() })}><RotateCcw size={16} />Rétablir</button>}
                  {vue === 'associe' && a.dossier_id && <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/dossiers/${a.dossier_id}`)}>Voir le dossier</button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {ajout && <AjoutAudio mode={ajout} onClose={() => setAjout(null)} onDone={(a) => { setAjout(null); setVue('a_traiter'); list.reload(); setMission(a) }} />}
      {mission && <NouveauDossier audioId={mission.id} audioClientId={mission.client_id} audioDuree={mission.duree_minutes}
        audioNom={mission.nom_fichier} onClose={() => { setMission(null); list.reload() }} />}
    </div>
  )
}

function AjoutAudio({ mode, onClose, onDone }: { mode: 'lien' | 'fichier'; onClose: () => void; onDone: (a: Audio) => void }) {
  const clients = useLoad(() => api.clients())
  const [url, setUrl] = useState('')
  const [nom, setNom] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [client, setClient] = useState('')
  const [duree, setDuree] = useState('')
  const { busy, error, run } = useAction()
  const envoyer = async () => {
    const a = await run(() => mode === 'lien'
      ? api.ajouterLien({ url, nom: nom || null, client_id: client || null, duree_minutes: duree ? Number(duree) : null })
      : api.ajouterFichier(file as File, client || undefined, duree || undefined))
    if (a) { toast('Audio enregistré'); onDone(a) }
  }
  return (
    <Modal title={mode === 'lien' ? 'Ajouter un lien OneDrive' : 'Déposer un fichier audio'} onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || (mode === 'lien' ? url.length < 10 : !file)} onClick={envoyer}>
          {busy ? 'Enregistrement…' : 'Enregistrer et créer la mission'}</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        {mode === 'lien' ? (
          <>
            <Field label="Lien de partage OneDrive ou SharePoint" hint="Le lien est chiffré et ne sera jamais communiqué aux retranscripteurs.">
              <input className="input" type="url" placeholder="https://…sharepoint.com/…" value={url} onChange={(e) => setUrl(e.target.value)} />
            </Field>
            <Field label="Nom de l'audio (facultatif)"><input className="input" value={nom} onChange={(e) => setNom(e.target.value)} /></Field>
            <Alert tone="info">La plateforme vérifie que le fichier est accessible avant de le proposer au retranscripteur.</Alert>
          </>
        ) : (
          <FileDrop accept=".mp3,.wav,.m4a,.mp4,.aac,.ogg,.flac,.webm,.wma" onFile={setFile}
            label={file ? `${file.name} · ${fSize(file.size)}` : 'Glissez le fichier audio ici ou cliquez'} hint="MP3, WAV, M4A, MP4… · 500 Mo maximum" />
        )}
        <div className="form-grid">
          <Field label="Client (facultatif)">
            <select className="input" value={client} onChange={(e) => setClient(e.target.value)}>
              <option value="">À préciser</option>
              {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
            </select>
          </Field>
          <Field label="Durée (minutes)"><input className="input" type="number" value={duree} onChange={(e) => setDuree(e.target.value)} /></Field>
        </div>
      </div>
    </Modal>
  )
}
