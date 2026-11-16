import { useState } from 'react'
import { AlertTriangle, CheckCircle2, UserCheck, Users } from 'lucide-react'
import { api, type DossierDetail, type Suggestion } from '@/lib/api'
import { fDate } from '@/lib/format'
import { Alert, Empty, ErrorBox, Field, Modal, PageLoader, Pill, StatutPill } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'

const FIABILITE: Record<string, { label: string; tone: string }> = {
  insuffisante: { label: 'Historique insuffisant', tone: 'gray' },
  limitee: { label: 'Historique limité', tone: 'amber' },
  bonne: { label: 'Historique fiable', tone: 'green' },
}

export function Attribution({ dossier, onChange }: { dossier: DossierDetail; onChange: () => void }) {
  const ouvert = dossier.statut_production === 'a_attribuer'
  const sugg = useLoad(() => ouvert ? api.suggestions(dossier.id) : Promise.resolve(null), [dossier.id, ouvert])
  const [choix, setChoix] = useState<Suggestion | null>(null)

  return (
    <div className="stack-lg">
      {dossier.affectations.length > 0 && (
        <div className="card">
          <div className="card-header"><h3 className="card-title">Historique des attributions</h3></div>
          <div className="list">
            {dossier.affectations.map((a) => (
              <div key={a.id} className="list-item">
                <span className="avatar">{a.prestataire_nom?.slice(0, 2).toUpperCase()}</span>
                <div className="list-main">
                  <div className="list-title">{a.prestataire_nom}</div>
                  <div className="small muted">Attribuée le {fDate(a.date_attribution)} · échéance {fDate(a.date_limite_rendu)}
                    {a.commentaire ? ` · consignes : ${a.commentaire}` : ''}</div>
                </div>
                <Pill tone={a.statut === 'rejete' ? 'gray' : a.statut === 'valide' ? 'green' : 'blue'}>
                  {{ en_attente: 'À commencer', en_cours: 'En cours', livre: 'PV livré', valide: 'Terminée', rejete: 'Retirée' }[a.statut] ?? a.statut}
                </Pill>
              </div>
            ))}
          </div>
        </div>
      )}

      {!ouvert ? (
        <Alert tone="info">
          L'attribution est possible lorsque le dossier est « à attribuer ». Étape actuelle : <StatutPill type="production" value={dossier.statut_production} />
        </Alert>
      ) : (
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Retranscripteurs suggérés</h3>
              <p className="small muted">Classement indicatif : la décision vous appartient. Les indicateurs ne sont jamais visibles des retranscripteurs.</p>
            </div>
          </div>
          <ErrorBox error={sugg.error} />
          {sugg.loading && !sugg.data ? <PageLoader /> : !sugg.data?.suggestions.length ? (
            <Empty icon={<Users size={24} />} title="Aucun retranscripteur actif">Ajoutez des retranscripteurs dans le référentiel.</Empty>
          ) : (
            <div className="list">
              {sugg.data.suggestions.map((s) => (
                <div key={s.prestataire_id} className="list-item" style={{ alignItems: 'flex-start' }}>
                  <div className="kpi-icon tone-primary mono" style={{ width: 44, height: 44, fontWeight: 650 }}
                    title="Score d'adéquation (0-100)">{s.score}</div>
                  <div className="list-main stack" style={{ gap: 6 }}>
                    <div className="row">
                      <span className="list-title">{s.nom}</span>
                      <Pill tone={FIABILITE[s.fiabilite_donnees].tone}>{FIABILITE[s.fiabilite_donnees].label}</Pill>
                      {!s.disponible && <Pill tone="red">Indisponible</Pill>}
                    </div>
                    <div className="row small" style={{ gap: 14 }}>
                      {s.raisons.map((r) => <span key={r} style={{ color: 'var(--green)' }}><CheckCircle2 size={13} style={{ verticalAlign: -2 }} /> {r}</span>)}
                      {s.alertes.map((r) => <span key={r} style={{ color: 'var(--amber)' }}><AlertTriangle size={13} style={{ verticalAlign: -2 }} /> {r}</span>)}
                    </div>
                  </div>
                  <button className={`btn ${s.rang === 1 ? 'btn-primary' : 'btn-secondary'} btn-sm`} onClick={() => setChoix(s)}>
                    <UserCheck size={16} />Choisir
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {choix && <ConfirmerAttribution dossier={dossier} choix={choix} onClose={() => setChoix(null)}
        onDone={() => { setChoix(null); onChange() }} />}
    </div>
  )
}

function ConfirmerAttribution({ dossier, choix, onClose, onDone }: {
  dossier: DossierDetail; choix: Suggestion; onClose: () => void; onDone: () => void
}) {
  const [echeance, setEcheance] = useState('')
  const [consignes, setConsignes] = useState('')
  const { busy, error, run } = useAction()
  const valider = async () => {
    const res = await run(() => api.attribuer(dossier.id, {
      prestataire_id: choix.prestataire_id, commentaire: consignes || null,
      date_limite_rendu: echeance ? new Date(`${echeance}T18:00:00`).toISOString() : null,
      confirmer_indisponible: !choix.disponible,
    }))
    if (res) { toast(`Mission attribuée à ${choix.nom}`); onDone() }
  }
  return (
    <Modal title={`Attribuer à ${choix.nom}`} onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" onClick={valider} disabled={busy}><UserCheck size={17} />Confirmer l'attribution</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        {!choix.disponible && <Alert tone="warning">Ce retranscripteur est indiqué indisponible. Confirmez uniquement si vous l'avez contacté.</Alert>}
        <Field label="Échéance de rendu" hint="Laisser vide : calcul automatique selon la durée de l'audio (7, 18 ou 25 jours, sans dépasser l'échéance client)">
          <input className="input" type="date" value={echeance} onChange={(e) => setEcheance(e.target.value)} />
        </Field>
        <Field label="Consignes pour le retranscripteur" hint="Visible par le retranscripteur">
          <textarea className="input" value={consignes} onChange={(e) => setConsignes(e.target.value)}
            placeholder="Ex. noms des intervenants, sigles particuliers…" />
        </Field>
        <p className="small muted">Le retranscripteur sera notifié et pourra télécharger l'audio depuis son espace, sans jamais accéder à OneDrive.</p>
      </div>
    </Modal>
  )
}
