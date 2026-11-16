import { useState } from 'react'
import { CalendarClock, Plus, Pencil, Trash2 } from 'lucide-react'
import { api, type RegleDelai } from '@/lib/api'
import { useAuth } from '@/lib/session'
import { fDate, fDuree, INSTANCES } from '@/lib/format'
import { aujourdhui } from '@/lib/tarifs'
import { Alert, Empty, ErrorBox, Field, Modal, PageLoader, Pill } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'

function conditions(r: RegleDelai): string {
  const c: string[] = []
  if (r.type_instance) c.push(`instance ${r.type_instance}`)
  if (r.duree_min_minutes != null && r.duree_max_minutes != null) c.push(`audio de plus de ${fDuree(r.duree_min_minutes)} à ${fDuree(r.duree_max_minutes)}`)
  else if (r.duree_min_minutes != null) c.push(`audio de plus de ${fDuree(r.duree_min_minutes)}`)
  else if (r.duree_max_minutes != null) c.push(`audio jusqu'à ${fDuree(r.duree_max_minutes)}`)
  if (r.urgence === true) c.push('dossier urgent')
  if (r.urgence === false) c.push('dossier non urgent')
  if (r.prestation === 'snp') c.push('sans prise de notes')
  if (r.prestation === 'special') c.push('prestation particulière')
  return c.length ? c.join(' · ') : 'Tous les dossiers (règle par défaut)'
}

export function Delais() {
  const { can } = useAuth()
  const gerer = can('tarifs.gerer')
  const { data, error, loading, reload } = useLoad(() => api.delais())
  const [edit, setEdit] = useState<RegleDelai | 'new' | null>(null)
  const action = useAction()

  if (loading && !data) return <PageLoader />
  return (
    <div className="stack-lg">
      <ErrorBox error={error ?? action.error} />
      <Alert tone="info">
        L'échéance prévisionnelle du PV final est calculée à partir de la <strong>date de réception de l'audio</strong> :
        la première règle applicable (dans l'ordre ci-dessous) fixe le délai. Modifier une règle ne change pas les échéances déjà fixées.
      </Alert>
      <div className="card">
        <div className="card-header">
          <h3 className="card-title row"><CalendarClock size={18} />Délais de réalisation</h3>
          {gerer && <button className="btn btn-primary btn-sm" onClick={() => setEdit('new')}><Plus size={15} />Nouvelle règle</button>}
        </div>
        {!data?.regles.length ? (
          <Empty icon={<CalendarClock size={24} />} title="Aucun délai paramétré">
            Sans règle, l'échéance de chaque dossier doit être saisie à la main.
          </Empty>
        ) : (
          <div className="table-wrap"><table>
            <thead><tr><th>Ordre</th><th>Règle</th><th>S'applique à</th><th>Délai</th><th /></tr></thead>
            <tbody>{data.regles.map((r) => (
              <tr key={r.id} style={{ opacity: r.actif ? 1 : .5 }}>
                <td className="mono">{r.priorite}</td>
                <td><strong>{r.libelle}</strong>{!r.actif && <> <Pill>Inactive</Pill></>}
                  {r.description && <div className="small muted">{r.description}</div>}</td>
                <td className="small">{conditions(r)}</td>
                <td><strong>{r.delai_jours} jour{r.delai_jours > 1 ? 's' : ''}</strong> <span className="small muted">{r.type_jours === 'ouvres' ? 'ouvrés' : 'calendaires'}</span></td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>{gerer && <>
                  <button className="btn btn-ghost btn-sm" onClick={() => setEdit(r)} aria-label="Modifier"><Pencil size={15} /></button>
                  <button className="btn btn-ghost btn-sm" aria-label="Supprimer" onClick={() => {
                    if (window.confirm(`Supprimer la règle « ${r.libelle} » ? Les échéances déjà fixées ne changent pas.`)) {
                      action.run(async () => { await api.supprimerRegleDelai(r.id); toast('Règle supprimée'); reload() })
                    }
                  }}><Trash2 size={15} /></button></>}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
      <div className="grid-2">
        {data && <Generaux generaux={data.generaux} gerer={gerer} onDone={reload} />}
        <SimulateurDelai />
      </div>
      {edit && <RegleEditeur regle={edit === 'new' ? null : edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
    </div>
  )
}

function Generaux({ generaux, gerer, onDone }: { generaux: { cle: string; libelle: string; valeur: number | null }[]; gerer: boolean; onDone: () => void }) {
  const [vals, setVals] = useState<Record<string, string>>(Object.fromEntries(generaux.map((g) => [g.cle, g.valeur == null ? '' : String(g.valeur)])))
  const { busy, error, run } = useAction()
  return (
    <div className="card card-pad stack">
      <h3 className="card-title">Autres paramètres de délais</h3>
      <ErrorBox error={error} />
      {generaux.map((g) => (
        <Field key={g.cle} label={g.libelle} hint={vals[g.cle] === '' ? 'Non défini : fonction désactivée' : undefined}>
          <input className="input" type="number" min={0} style={{ maxWidth: 140 }} disabled={!gerer} value={vals[g.cle]}
            onChange={(e) => setVals({ ...vals, [g.cle]: e.target.value })} />
        </Field>
      ))}
      {gerer && <button className="btn btn-secondary" style={{ alignSelf: 'flex-start' }} disabled={busy} onClick={async () => {
        const valeurs = Object.fromEntries(Object.entries(vals).map(([k, v]) => [k, v === '' ? null : Number(v)]))
        if (await run(() => api.parametresGeneraux(valeurs))) { toast('Paramètres enregistrés'); onDone() }
      }}>Enregistrer</button>}
    </div>
  )
}

function SimulateurDelai() {
  const [f, setF] = useState({ date_reception: aujourdhui(), type_instance: 'CE', duree_minutes: '60', urgence: false })
  const [res, setRes] = useState<Awaited<ReturnType<typeof api.simulerDelai>> | null>(null)
  const { busy, error, run } = useAction()
  return (
    <div className="card card-pad stack">
      <h3 className="card-title">Tester un délai</h3>
      <ErrorBox error={error} />
      <div className="form-grid">
        <Field label="Réception de l'audio"><input className="input" type="date" value={f.date_reception} onChange={(e) => setF({ ...f, date_reception: e.target.value })} /></Field>
        <Field label="Instance"><select className="input" value={f.type_instance} onChange={(e) => setF({ ...f, type_instance: e.target.value })}>{INSTANCES.map((i) => <option key={i}>{i}</option>)}</select></Field>
        <Field label="Durée de l'audio (minutes)"><input className="input" type="number" min={0} value={f.duree_minutes} onChange={(e) => setF({ ...f, duree_minutes: e.target.value })} /></Field>
        <label className="checkbox" style={{ alignSelf: 'end' }}><input type="checkbox" checked={f.urgence} onChange={(e) => setF({ ...f, urgence: e.target.checked })} />Urgent</label>
      </div>
      <button className="btn btn-secondary" style={{ alignSelf: 'flex-start' }} disabled={busy} onClick={async () => {
        const r = await run(() => api.simulerDelai({ ...f, duree_minutes: f.duree_minutes === '' ? null : Number(f.duree_minutes) }))
        if (r) setRes(r)
      }}>Calculer l'échéance</button>
      {res && (res.echeance
        ? <div className="callout"><strong>Échéance : {fDate(res.echeance)}</strong><div className="small muted">Règle « {res.detail?.regle} » · {res.detail?.delai_jours} jour(s) {res.detail?.type_jours === 'ouvres' ? 'ouvrés' : 'calendaires'}</div></div>
        : <Alert tone="warning">{res.message}</Alert>)}
    </div>
  )
}

function RegleEditeur({ regle, onClose, onDone }: { regle: RegleDelai | null; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({
    libelle: regle?.libelle ?? '', priorite: String(regle?.priorite ?? 100), actif: regle?.actif ?? true,
    type_instance: regle?.type_instance ?? '', duree_min: regle?.duree_min_minutes != null ? String(regle.duree_min_minutes) : '',
    duree_max: regle?.duree_max_minutes != null ? String(regle.duree_max_minutes) : '',
    urgence: regle?.urgence == null ? '' : regle.urgence ? 'oui' : 'non', prestation: regle?.prestation ?? '',
    delai_jours: regle ? String(regle.delai_jours) : '', type_jours: regle?.type_jours ?? 'calendaires', description: regle?.description ?? '',
  })
  const { busy, error, run } = useAction()
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  const enregistrer = async () => {
    const body = {
      libelle: f.libelle, priorite: Number(f.priorite || 100), actif: f.actif, type_instance: f.type_instance || null,
      duree_min_minutes: f.duree_min === '' ? null : Number(f.duree_min), duree_max_minutes: f.duree_max === '' ? null : Number(f.duree_max),
      urgence: f.urgence === '' ? null : f.urgence === 'oui', prestation: f.prestation || null,
      delai_jours: Number(f.delai_jours), type_jours: f.type_jours, description: f.description || null,
    }
    if (await run(() => regle ? api.modifierRegleDelai(regle.id, body) : api.creerRegleDelai(body))) { toast('Règle enregistrée'); onDone() }
  }
  return (
    <Modal title={regle ? `Modifier « ${regle.libelle} »` : 'Nouvelle règle de délai'} onClose={onClose} large
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || f.libelle.length < 2 || f.delai_jours === ''} onClick={enregistrer}>Enregistrer</button></>}>
      <div className="stack-lg">
        <ErrorBox error={error} />
        <div className="form-grid">
          <Field label="Nom de la règle" full><input className="input" value={f.libelle} onChange={set('libelle')} placeholder="Ex. CSSCT — audio court" /></Field>
          <Field label="Délai de réalisation (jours après réception de l'audio)"><input className="input" type="number" min={0} value={f.delai_jours} onChange={set('delai_jours')} /></Field>
          <Field label="Décompte"><select className="input" value={f.type_jours} onChange={set('type_jours')}>
            <option value="calendaires">Jours calendaires</option><option value="ouvres">Jours ouvrés (lundi–vendredi)</option></select></Field>
        </div>
        <div className="card card-pad stack" style={{ background: 'var(--surface-2)' }}>
          <div className="section-title" style={{ fontSize: 15 }}>Conditions <span className="small muted">(laisser vide = indifférent)</span></div>
          <div className="form-grid">
            <Field label="Type d'instance"><select className="input" value={f.type_instance} onChange={set('type_instance')}>
              <option value="">Toutes</option>{INSTANCES.map((i) => <option key={i}>{i}</option>)}</select></Field>
            <Field label="Urgence"><select className="input" value={f.urgence} onChange={set('urgence')}>
              <option value="">Indifférent</option><option value="oui">Dossiers urgents</option><option value="non">Dossiers non urgents</option></select></Field>
            <Field label="Durée de l'audio : plus de (minutes)"><input className="input" type="number" min={0} value={f.duree_min} onChange={set('duree_min')} /></Field>
            <Field label="… et jusqu'à (minutes)"><input className="input" type="number" min={1} value={f.duree_max} onChange={set('duree_max')} /></Field>
            <Field label="Type de prestation"><select className="input" value={f.prestation} onChange={set('prestation')}>
              <option value="">Toutes</option><option value="snp">Sans prise de notes</option><option value="special">Prestation particulière</option></select></Field>
            <Field label="Ordre d'évaluation" hint="Les règles sont testées de la plus petite à la plus grande valeur"><input className="input" type="number" min={0} value={f.priorite} onChange={set('priorite')} /></Field>
          </div>
          <label className="checkbox"><input type="checkbox" checked={f.actif} onChange={(e) => setF({ ...f, actif: e.target.checked })} />Règle active</label>
        </div>
        <Field label="Note (facultatif)"><textarea className="input" value={f.description} onChange={set('description')} /></Field>
      </div>
    </Modal>
  )
}
