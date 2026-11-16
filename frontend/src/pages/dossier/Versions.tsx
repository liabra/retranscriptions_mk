import { useState } from 'react'
import { Download, FileText, GitCompare } from 'lucide-react'
import { api, type DossierDetail, type Livraison } from '@/lib/api'
import { downloadFile } from '@/services/api'
import { useAuth } from '@/lib/session'
import { fDateTime, fSize } from '@/lib/format'
import { Empty, ErrorBox, FileDrop, Modal, PageLoader, Pill, StatutPill } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'
import { RapportConformite } from '@/components/Rapport'

export function Versions({ dossier, onChange }: { dossier: DossierDetail; onChange: () => void }) {
  const { can } = useAuth()
  const [comparer, setComparer] = useState<[Livraison, Livraison] | null>(null)
  const [deposer, setDeposer] = useState(false)
  const livs = dossier.livraisons
  const peutDeposer = can('relecture') && ['livre', 'a_relire', 'a_controler'].includes(dossier.statut_production)
  const action = useAction()

  const telecharger = (l: Livraison) =>
    action.run(() => downloadFile(`/livraisons/${l.id}/fichier`, `PV_${dossier.reference}_v${l.version}.docx`))

  return (
    <div className="stack-lg">
      <ErrorBox error={action.error} />
      {peutDeposer && (
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={() => setDeposer(true)}><FileText size={17} />Déposer une version corrigée</button>
        </div>
      )}
      {!livs.length && <Empty icon={<FileText size={24} />} title="Aucun PV déposé">Les versions déposées par le retranscripteur apparaîtront ici avec leur contrôle de conformité.</Empty>}
      {livs.map((l, i) => {
        const precedente = livs[i + 1]
        const corrections = dossier.corrections.filter((c) => c.livraison_id === l.id)
        return (
          <div key={l.id} className="card">
            <div className="card-header">
              <div className="row">
                <span className="kpi-icon tone-primary" style={{ width: 36, height: 36 }}><FileText size={18} /></span>
                <div>
                  <div style={{ fontWeight: 600 }}>
                    Version {l.version}{i === 0 && <Pill tone="primary">Dernière</Pill>}
                  </div>
                  <div className="small muted">
                    {l.type_depot === 'correction_interne' ? 'Correction interne' : 'Dépôt retranscripteur'} · {l.depose_par} · {fDateTime(l.depose_le)} · {fSize(l.taille_octets)}
                  </div>
                </div>
              </div>
              <div className="row">
                <StatutPill type="controle" value={l.statut_controle} />
                {precedente && (
                  <button className="btn btn-ghost btn-sm" onClick={() => setComparer([precedente, l])}>
                    <GitCompare size={16} />Comparer à v{precedente.version}
                  </button>
                )}
                {(can('relecture') || can('validation') || can('dossiers.gerer')) && (
                  <button className="btn btn-secondary btn-sm" onClick={() => telecharger(l)} disabled={action.busy}>
                    <Download size={16} />Télécharger
                  </button>
                )}
              </div>
            </div>
            <div className="card-body stack">
              {l.commentaire && <div className="callout small"><strong>Message du déposant :</strong> {l.commentaire}</div>}
              <RapportConformite rapport={l.rapport_controle} />
              {corrections.map((c) => (
                <div key={c.id} className="callout callout-amber small">
                  <strong>Correction demandée par {c.demandee_par} · {fDateTime(c.created_at)}</strong>
                  <div style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>{c.message}</div>
                </div>
              ))}
            </div>
          </div>
        )
      })}
      {comparer && <Comparaison a={comparer[0]} b={comparer[1]} onClose={() => setComparer(null)} />}
      {deposer && <DepotInterne dossierId={dossier.id} onClose={() => setDeposer(false)} onDone={() => { setDeposer(false); onChange() }} />}
    </div>
  )
}

function Comparaison({ a, b, onClose }: { a: Livraison; b: Livraison; onClose: () => void }) {
  const { data, error } = useLoad(() => api.comparer(a.id, b.id), [a.id, b.id])
  return (
    <Modal title={`Comparaison v${a.version} → v${b.version}`} onClose={onClose} large>
      <ErrorBox error={error} />
      {!data && !error ? <PageLoader /> : data && (
        <div className="stack">
          <p className="muted small">{data.modifications} passage(s) modifié(s). Comparaison du texte paragraphe par paragraphe (la mise en forme n'est pas comparée).</p>
          {data.blocs.map((bloc, i) => bloc.type === 'identique' ? (
            <div key={i} className="small muted" style={{ textAlign: 'center' }}>· · · {bloc.nombre} paragraphe(s) identique(s) · · ·</div>
          ) : (
            <div key={i} className="stack" style={{ gap: 6 }}>
              {bloc.avant?.map((t, j) => <div key={`a${j}`} className="diff-del">− {t}</div>)}
              {bloc.apres?.map((t, j) => <div key={`b${j}`} className="diff-add">+ {t}</div>)}
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}

function DepotInterne({ dossierId, onClose, onDone }: { dossierId: string; onClose: () => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [commentaire, setCommentaire] = useState('')
  const { busy, error, run } = useAction()
  const envoyer = async () => {
    if (!file) return
    const res = await run(() => api.deposerInterne(dossierId, file, commentaire))
    if (res) { toast(`Version ${res.version} enregistrée`); onDone() }
  }
  return (
    <Modal title="Déposer une version corrigée" onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={!file || busy} onClick={envoyer}>{busy ? 'Contrôle en cours…' : 'Déposer'}</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        <p className="small muted">La version corrigée par l'équipe est ajoutée à l'historique ; elle ne remplace jamais les versions précédentes.</p>
        <FileDrop accept=".docx" onFile={setFile} label={file ? file.name : 'Choisir le fichier Word (.docx)'} hint="Comic Sans MS 12 pt · 25 Mo maximum" />
        <textarea className="input" placeholder="Commentaire (facultatif)" value={commentaire} onChange={(e) => setCommentaire(e.target.value)} />
      </div>
    </Modal>
  )
}
