import { useState } from 'react'
import { AudioLines, CalendarClock, CheckCircle2, ClipboardList, Clock, Download, FileText, Flame, MessageSquareWarning, PlayCircle, Upload } from 'lucide-react'
import { api, type Mission } from '@/lib/api'
import { downloadFile } from '@/services/api'
import { useAuth } from '@/lib/session'
import { fDate, fDateTime, fDuree, fSize, relative } from '@/lib/format'
import { Alert, Empty, ErrorBox, FileDrop, PageLoader, Pill, StatutPill, Tabs } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'
import { RapportConformite } from '@/components/Rapport'

const ETAPE_TONE: Record<string, string> = {
  a_commencer: 'blue', en_cours: 'blue', livre: 'violet', en_relecture: 'violet', correction: 'amber', termine: 'green',
}

export function MesMissionsPage() {
  const { user } = useAuth()
  const [vue, setVue] = useState<'cours' | 'terminees'>('cours')
  const { data, error, loading, reload, setData } = useLoad(() => api.missions(vue === 'terminees'), [vue])
  const enRetard = data?.filter((m) => m.en_retard).length ?? 0

  const maj = (m: Mission) => setData((data ?? []).map((x) => (x.affectation_id === m.affectation_id ? m : x)))

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Bonjour {user?.nom.split(' ')[0]}</h1>
          <p>{vue === 'cours' ? `${data?.length ?? 0} mission(s) en cours${enRetard ? ` · ${enRetard} en retard` : ''}` : 'Vos missions validées'}</p>
        </div>
      </div>
      <Tabs value={vue} onChange={setVue} items={[{ key: 'cours', label: 'En cours' }, { key: 'terminees', label: 'Terminées' }]} />
      <ErrorBox error={error} />
      {loading && !data ? <PageLoader /> : !data?.length ? (
        <div className="card"><Empty icon={<ClipboardList size={24} />} title={vue === 'cours' ? 'Aucune mission en cours' : 'Aucune mission terminée'}>
          {vue === 'cours' ? 'Vous serez prévenu(e) dès qu’une nouvelle mission vous sera attribuée.' : ''}</Empty></div>
      ) : (
        <div className="stack-lg">
          {data.map((m) => <MissionCard key={m.affectation_id} m={m} onChange={maj} onReload={reload} />)}
        </div>
      )}
    </div>
  )
}

function MissionCard({ m, onChange, onReload }: { m: Mission; onChange: (m: Mission) => void; onReload: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [commentaire, setCommentaire] = useState('')
  const [historique, setHistorique] = useState(false)
  const action = useAction()
  const rel = relative(m.echeance)
  const correction = m.corrections.find((c) => !c.resolue_le)
  const derniere = m.versions[0]
  const termine = m.etape === 'termine'

  const telecharger = () => action.run(async () => {
    await downloadFile(`/espace-prestataire/missions/${m.affectation_id}/audio`, `Audio_${m.reference}`)
    onReload()
  })
  const deposer = async () => {
    if (!file) return
    const res = await action.run(() => api.deposerPV(m.affectation_id, file, commentaire))
    if (res) {
      onChange(res)
      setFile(null)
      setCommentaire('')
      const v = res.versions[0]
      toast(v?.statut_controle === 'non_conforme' ? 'PV déposé — la mise en forme doit être corrigée' : 'PV déposé, merci !', v?.statut_controle === 'non_conforme')
    }
  }

  return (
    <article className="card">
      <div className="mission">
        <div className="mission-top">
          <div>
            <div className="mission-ref">{m.reference} · {m.type_instance}</div>
            <h2 className="mission-title">{m.titre ?? 'Retranscription'}</h2>
            {m.instance && <div className="muted">{m.instance}</div>}
          </div>
          <div className="row">
            {m.urgent && <Pill tone="red"><Flame size={13} />Prioritaire</Pill>}
            <Pill tone={ETAPE_TONE[m.etape] ?? 'gray'} dot>{m.etape_label}</Pill>
          </div>
        </div>

        <div className="mission-facts">
          {!termine && <span className={`deadline tone-${m.en_retard ? 'red' : rel.tone}`}><CalendarClock size={16} />À rendre le {fDate(m.echeance)} · {rel.texte}</span>}
          <span><Clock size={16} />{fDuree(m.duree_audio_minutes)} d'audio</span>
          {m.date_seance && <span><CalendarClock size={16} />Séance du {fDate(m.date_seance)}</span>}
        </div>

        {m.consignes && <div className="callout small"><strong>Consignes :</strong> {m.consignes}</div>}
        {correction && (
          <div className="callout callout-amber">
            <div className="row" style={{ fontWeight: 600 }}><MessageSquareWarning size={17} />Correction demandée le {fDate(correction.created_at)}</div>
            <p style={{ whiteSpace: 'pre-wrap', marginTop: 6 }}>{correction.message}</p>
            {correction.date_limite && <p className="small" style={{ marginTop: 6 }}>Nouvelle échéance : {fDate(correction.date_limite)}</p>}
          </div>
        )}
        <ErrorBox error={action.error} />

        {!termine && (
          <div className="grid-2">
            <div className="stack" style={{ gap: 10 }}>
              <div className="section-title row"><AudioLines size={18} />1. L'audio</div>
              {m.audio?.disponible ? (
                <>
                  <button className="btn btn-secondary btn-lg" onClick={telecharger} disabled={action.busy}>
                    <Download size={18} />Télécharger l'audio
                  </button>
                  <span className="hint">{m.audio.nom_fichier} · {fSize(m.audio.taille_octets)}</span>
                </>
              ) : <Alert tone="warning">L'audio n'est pas encore disponible. L'équipe A2C a été informée.</Alert>}
              {m.etape === 'a_commencer' && (
                <button className="btn btn-ghost btn-sm" onClick={() => action.run(async () => onChange(await api.commencer(m.affectation_id)))}>
                  <PlayCircle size={16} />Indiquer que je commence
                </button>
              )}
            </div>
            <div className="stack" style={{ gap: 10 }}>
              <div className="section-title row"><Upload size={18} />2. Mon PV</div>
              {m.peut_deposer ? (
                <>
                  <FileDrop accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onFile={setFile}
                    label={file ? file.name : correction ? 'Déposer la version corrigée' : derniere ? 'Remplacer par une nouvelle version' : 'Glissez votre PV Word ici'}
                    hint="Format .docx · police Comic Sans MS · taille 12" />
                  {file && <>
                    <textarea className="input" placeholder="Message pour la relectrice (facultatif)" value={commentaire} onChange={(e) => setCommentaire(e.target.value)} />
                    <button className="btn btn-primary btn-lg" onClick={deposer} disabled={action.busy}>
                      <Upload size={18} />{action.busy ? 'Contrôle du document…' : 'Envoyer mon PV'}
                    </button>
                  </>}
                </>
              ) : <Alert tone="info">Votre PV est en relecture. Vous serez prévenu(e) si une correction est nécessaire.</Alert>}
            </div>
          </div>
        )}

        {derniere && (
          <div className="callout stack" style={{ gap: 10 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div className="row"><FileText size={17} /><strong>Version {derniere.version}</strong><span className="small muted">déposée le {fDateTime(derniere.depose_le)}</span></div>
              <StatutPill type="controle" value={derniere.statut_controle} />
            </div>
            <RapportConformite rapport={derniere.rapport_controle} ouvert={derniere.statut_controle === 'non_conforme'} />
            {m.versions.length > 1 && (
              <button className="btn btn-ghost btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => setHistorique(!historique)}>
                {historique ? 'Masquer' : 'Voir'} les {m.versions.length} versions
              </button>
            )}
            {historique && m.versions.map((v) => (
              <div key={v.id} className="row small" style={{ justifyContent: 'space-between' }}>
                <span>Version {v.version} · {fDateTime(v.depose_le)} · {v.nom_original}</span>
                <span className="row">
                  <StatutPill type="controle" value={v.statut_controle} />
                  <button className="btn btn-ghost btn-sm" onClick={() => action.run(() => downloadFile(`/espace-prestataire/livraisons/${v.id}/fichier`, v.nom_original))}><Download size={14} /></button>
                </span>
              </div>
            ))}
          </div>
        )}
        {termine && <div className="row" style={{ color: 'var(--green)', fontWeight: 600 }}><CheckCircle2 size={18} />Mission validée — merci pour votre travail.</div>}
      </div>
    </article>
  )
}

export function EspaceClientPage() {
  const dossiers = useLoad(() => api.clientDossiers())
  const depots = useLoad(() => api.clientDepots())
  const [file, setFile] = useState<File | null>(null)
  const [commentaire, setCommentaire] = useState('')
  const action = useAction()
  const envoyer = async () => {
    if (!file) return
    if (await action.run(() => api.clientDeposer(file, commentaire))) {
      toast('Audio transmis à A2C')
      setFile(null); setCommentaire(''); depots.reload()
    }
  }
  return (
    <div className="page">
      <div className="page-head"><div><h1>Mon espace</h1><p>Transmettez vos enregistrements et suivez l'avancement de vos procès-verbaux.</p></div></div>
      <div className="split">
        <div className="card">
          <div className="card-header"><h3 className="card-title">Mes dossiers</h3></div>
          {dossiers.loading && !dossiers.data ? <PageLoader /> : !dossiers.data?.length ? <Empty icon={<FileText size={24} />} title="Aucun dossier pour le moment" /> : (
            <div className="list">{dossiers.data.map((d) => (
              <div key={d.reference} className="list-item">
                <div className="list-main"><div className="list-title">{d.titre ?? d.reference}</div>
                  <div className="small muted">{d.reference} · {d.type_instance}{d.date_seance ? ` · séance du ${fDate(d.date_seance)}` : ''}</div></div>
                <Pill tone={d.etape === 'Terminé' ? 'green' : 'blue'} dot>{d.etape}</Pill>
              </div>
            ))}</div>
          )}
        </div>
        <div className="stack-lg">
          <div className="card card-pad stack">
            <h3 className="card-title">Envoyer un enregistrement</h3>
            <ErrorBox error={action.error} />
            <FileDrop accept=".mp3,.wav,.m4a,.mp4,.aac,.ogg,.flac" onFile={setFile} label={file ? file.name : 'Choisir le fichier audio'} hint="MP3, WAV, M4A… · 500 Mo maximum" />
            <textarea className="input" placeholder="Informations utiles (date de séance, intervenants…)" value={commentaire} onChange={(e) => setCommentaire(e.target.value)} />
            <button className="btn btn-primary" disabled={!file || action.busy} onClick={envoyer}>{action.busy ? 'Envoi…' : 'Envoyer'}</button>
          </div>
          {!!depots.data?.length && (
            <div className="card">
              <div className="card-header"><h3 className="card-title">Mes envois</h3></div>
              <div className="list">{depots.data.map((d) => (
                <div key={d.id} className="list-item small">
                  <div className="list-main ellipsis">{d.nom_fichier}<div className="muted">{fDateTime(d.created_at)}</div></div>
                  <Pill tone={d.pris_en_charge ? 'green' : 'gray'}>{d.pris_en_charge ? 'Pris en charge' : 'Reçu'}</Pill>
                </div>
              ))}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
