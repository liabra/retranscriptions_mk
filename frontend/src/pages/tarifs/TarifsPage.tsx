import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Calculator, ChevronDown, ChevronUp, History, Pencil, Percent, Plus, Power, Send, ShieldCheck, Trash2 } from 'lucide-react'
import { api, type FamilleTarif, type Simulation, type VersionTarif } from '@/lib/api'
import { useAuth } from '@/lib/session'
import { fDate, fMoney, INSTANCES } from '@/lib/format'
import { aujourdhui, libelleConditions, libelleMajoration, libellesTranches, periode, STATUT_TARIF } from '@/lib/tarifs'
import { Alert, Empty, ErrorBox, Field, Modal, PageLoader, Pill, Tabs } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'
import { GrilleEditeur, MajorationEditeur } from './Editeurs'
import { Delais } from './Delais'

type Onglet = 'client' | 'retranscripteur' | 'majorations' | 'delais' | 'simulateur'

export function TarifsPage() {
  const [params, setParams] = useSearchParams()
  const onglet = (params.get('onglet') as Onglet) || 'client'
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Tarifs et paramètres commerciaux</h1>
          <p>Barèmes, rémunérations, majorations et délais. Chaque modification crée une nouvelle version datée : rien n'est jamais modifié rétroactivement.</p>
        </div>
      </div>
      <div data-tour="tarifs-onglets"><Tabs value={onglet} onChange={(o) => setParams({ onglet: o })} items={[
        { key: 'client', label: 'Tarifs clients' }, { key: 'retranscripteur', label: 'Rémunération des retranscripteurs' },
        { key: 'majorations', label: 'Majorations' }, { key: 'delais', label: 'Délais de réalisation' },
        { key: 'simulateur', label: 'Simulateur' },
      ]} /></div>
      {(onglet === 'client' || onglet === 'retranscripteur') && <Grilles usage={onglet} />}
      {onglet === 'majorations' && <Majorations />}
      {onglet === 'delais' && <Delais />}
      {onglet === 'simulateur' && <Simulateur />}
    </div>
  )
}

function Statut({ v }: { v: VersionTarif }) {
  const s = STATUT_TARIF[v.statut]
  return <Pill tone={s.tone} dot>{s.label}</Pill>
}

function applicationLabel(f: FamilleTarif, v: VersionTarif, usage: string) {
  if (v.application === 'instance') return `Instances ${v.type_instance}`
  if (v.application === 'attribuee') {
    return f.attribuee_a.length ? `Attribuée à : ${f.attribuee_a.join(', ')}` : `Sur attribution (aucun${usage === 'client' ? ' client' : ' retranscripteur'} pour l'instant)`
  }
  return usage === 'client' ? 'Grille par défaut — tous les clients' : 'Grille par défaut — tous les retranscripteurs'
}

function TranchesTable({ v }: { v: VersionTarif }) {
  if (!v.tranches) {
    return (
      <div className="stack small">
        <span className="muted">Cette grille utilise des règles avancées :</span>
        {v.regles.map((r, i) => <span key={i}>• {r.libelle}</span>)}
        <Link to={`/grilles/${v.id}`} className="small">Ouvrir l'éditeur de règles avancées</Link>
      </div>
    )
  }
  return (
    <div className="grid-2" style={{ gap: '6px 24px' }}>
      {libellesTranches(v.tranches).map((t, i) => (
        <div key={i} className="row" style={{ justifyContent: 'space-between', borderBottom: '1px dashed var(--line)', padding: '6px 0' }}>
          <span className="muted">{t.libelle}</span><strong className="mono">{t.prix}</strong>
        </div>
      ))}
    </div>
  )
}

/** Actions communes à une famille (historique, brouillon, activation). */
function useFamilleActions(reload: () => void) {
  const action = useAction()
  const go = (fn: () => Promise<unknown>, msg: string) => action.run(async () => { await fn(); toast(msg); reload() })
  return { ...action, go }
}

function Historique({ f, onAction, peutGerer }: { f: FamilleTarif; onAction: (fn: () => Promise<unknown>, msg: string) => void; peutGerer: boolean }) {
  return (
    <div className="table-wrap" style={{ marginTop: 8 }}>
      <table>
        <thead><tr><th>Version</th><th>État</th><th>Période d'application</th><th>Contenu</th><th>Créée par</th><th /></tr></thead>
        <tbody>{f.versions.map((v) => (
          <tr key={v.id}>
            <td className="mono">v{v.version}<div className="small muted">{v.nom}</div></td>
            <td><Statut v={v} />{v.utilisee && <div className="small muted" style={{ marginTop: 4 }}>utilisée dans des calculs</div>}</td>
            <td className="small">{periode(v)}</td>
            <td className="small">{v.majoration ? libelleMajoration(v) : v.tranches ? `${v.tranches.length} tranche(s)` : 'Règles avancées'}</td>
            <td className="small">{v.creee_par ?? 'Initialisation'}<div className="muted">{fDate(v.date_creation)}</div></td>
            <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
              {peutGerer && !v.brouillon && v.active && v.statut !== 'archivee' && (
                <button className="btn btn-ghost btn-sm" onClick={() => {
                  if (window.confirm(`Désactiver la version ${v.version} ? Elle ne sera plus appliquée aux nouveaux calculs.`)) onAction(() => api.desactiverGrille(v.id), 'Version désactivée')
                }}><Power size={14} />Désactiver</button>
              )}
              {peutGerer && v.statut === 'desactivee' && (
                <button className="btn btn-ghost btn-sm" onClick={() => onAction(() => api.activerGrille(v.id), 'Version réactivée')}><Power size={14} />Réactiver</button>
              )}
              {v.avancee && <Link className="btn btn-ghost btn-sm" to={`/grilles/${v.id}`}>Règles</Link>}
            </td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}

function BrouillonBar({ v, onEdit, onAction }: { v: VersionTarif; onEdit: () => void; onAction: (fn: () => Promise<unknown>, msg: string) => void }) {
  const [publier, setPublier] = useState(false)
  return (
    <div className="callout callout-amber row" style={{ justifyContent: 'space-between' }}>
      <span><strong>Brouillon v{v.version}</strong> en préparation — sans effet tant qu'il n'est pas publié.</span>
      <span className="row">
        <button className="btn btn-ghost btn-sm" onClick={onEdit}><Pencil size={14} />Modifier</button>
        <button className="btn btn-ghost btn-sm" onClick={() => { if (window.confirm('Supprimer ce brouillon ?')) onAction(() => api.supprimerBrouillon(v.id), 'Brouillon supprimé') }}><Trash2 size={14} />Supprimer</button>
        <button className="btn btn-primary btn-sm" onClick={() => setPublier(true)}><Send size={14} />Publier</button>
      </span>
      {publier && <Publier v={v} onClose={() => setPublier(false)} onDone={() => { setPublier(false); onAction(async () => undefined, 'Publié') }} />}
    </div>
  )
}

function Publier({ v, onClose, onDone }: { v: VersionTarif; onClose: () => void; onDone: () => void }) {
  const [date, setDate] = useState(aujourdhui())
  const { busy, error, run } = useAction()
  return (
    <Modal title={`Publier « ${v.nom} » v${v.version}`} onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || !date} onClick={async () => { if (await run(() => api.publier(v.id, date))) onDone() }}>Publier</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        <Field label="Appliquer à partir du"><input className="input" type="date" min={aujourdhui()} value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <Alert tone="info">La version précédente reste valable pour les dossiers dont l'audio a été reçu avant cette date. Les calculs et factures validés ne changent pas.</Alert>
      </div>
    </Modal>
  )
}

/* ── Grilles à tranches ──────────────────────────────────────────────────── */
function Grilles({ usage }: { usage: 'client' | 'retranscripteur' }) {
  const { can } = useAuth()
  const gerer = can('tarifs.gerer')
  const { data, error, loading, reload } = useLoad(() => api.catalogue(usage), [usage])
  const [edit, setEdit] = useState<{ source: VersionTarif | null; annuel?: boolean } | null>(null)
  const [ouvert, setOuvert] = useState<string | null>(null)
  const actions = useFamilleActions(reload)
  const anneeSuivante = new Date().getFullYear() + 1

  if (loading && !data) return <PageLoader />
  return (
    <div className="stack-lg">
      <ErrorBox error={error ?? actions.error} />
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <p className="muted small" style={{ maxWidth: 720 }}>
          {usage === 'client'
            ? 'Le tarif appliqué est choisi à la date de réception de l’audio : grille attribuée au client, sinon grille du type d’instance, sinon grille par défaut.'
            : 'La rémunération utilise la grille attribuée au retranscripteur sur sa fiche, sinon la grille par défaut.'}
        </p>
        {gerer && <button className="btn btn-primary" onClick={() => setEdit({ source: null })}><Plus size={17} />Nouvelle grille</button>}
      </div>
      {!data?.length && <div className="card"><Empty icon={<Calculator size={24} />} title="Aucune grille" /></div>}
      {data?.map((f) => {
        const v = f.courante ?? f.brouillon ?? f.versions[0]
        return (
          <section key={f.famille_id} className="card">
            <div className="card-header">
              <div>
                <div className="row"><h3 className="card-title">{f.nom}</h3>{v && <Statut v={v} />}{v && <span className="small muted">v{v.version}</span>}</div>
                <div className="small muted">{v && applicationLabel(f, v, usage)} · {v && periode(v)}</div>
              </div>
              <div className="row">
                {gerer && v && !f.brouillon && !v.avancee && <>
                  <button className="btn btn-secondary btn-sm" onClick={() => setEdit({ source: v, annuel: true })}><Plus size={15} />Barème {anneeSuivante}</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setEdit({ source: v })}><Pencil size={15} />Modifier</button>
                </>}
                <button className="btn btn-ghost btn-sm" onClick={() => setOuvert(ouvert === f.famille_id ? null : f.famille_id)} aria-expanded={ouvert === f.famille_id}>
                  <History size={15} />Historique ({f.versions.length}){ouvert === f.famille_id ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </button>
              </div>
            </div>
            <div className="card-body stack">
              {f.programmee && f.courante?.id !== f.programmee.id && (
                <Alert tone="info">Nouvelle version v{f.programmee.version} programmée à partir du {fDate(f.programmee.date_debut)}.</Alert>
              )}
              {f.brouillon && gerer && <BrouillonBar v={f.brouillon} onEdit={() => setEdit({ source: f.brouillon })} onAction={actions.go} />}
              {v && <TranchesTable v={v} />}
              {v?.description && <p className="small muted">{v.description}</p>}
              {ouvert === f.famille_id && <Historique f={f} onAction={actions.go} peutGerer={gerer} />}
            </div>
          </section>
        )
      })}
      {edit && <GrilleEditeur usage={usage} source={edit.source} datePublication={edit.annuel ? `${anneeSuivante}-01-01` : undefined}
        onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
    </div>
  )
}

/* ── Majorations ─────────────────────────────────────────────────────────── */
function Majorations() {
  const { can } = useAuth()
  const gerer = can('tarifs.gerer')
  const { data, error, loading, reload } = useLoad(() => api.catalogue('majorations'))
  const [edit, setEdit] = useState<{ source: VersionTarif | null } | null>(null)
  const [ouvert, setOuvert] = useState<string | null>(null)
  const actions = useFamilleActions(reload)
  const existants = new Set(data?.map((f) => f.type))
  const disponibles = (['urgence', 'snp', 'special'] as const).filter((t) => !existants.has(t))

  if (loading && !data) return <PageLoader />
  return (
    <div className="stack-lg">
      <ErrorBox error={error ?? actions.error} />
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <p className="muted small" style={{ maxWidth: 720 }}>Une majoration s'ajoute au tarif de base. Elle peut s'appliquer au tarif client, à la rémunération du retranscripteur, ou aux deux, indépendamment.</p>
        {gerer && disponibles.length > 0 && <button className="btn btn-primary" onClick={() => setEdit({ source: null })}><Plus size={17} />Nouvelle majoration</button>}
      </div>
      <div className="grid-2">
        {data?.map((f) => {
          const v = f.courante ?? f.brouillon ?? f.versions[0]
          if (!v) return null
          return (
            <section key={f.famille_id} className="card" style={ouvert === f.famille_id ? { gridColumn: '1 / -1' } : undefined}>
              <div className="card-header">
                <div className="row"><span className="kpi-icon tone-amber"><Percent size={17} /></span><h3 className="card-title">{f.nom}</h3></div>
                <Statut v={v} />
              </div>
              <div className="card-body stack">
                <div style={{ fontSize: 30, fontWeight: 650, color: f.courante ? undefined : 'var(--faint)' }} className="mono">{libelleMajoration(v)}</div>
                <div className="row">
                  <Pill tone={v.applique_client ? 'green' : 'gray'}>{v.applique_client ? '✓' : '✕'} Tarif client</Pill>
                  <Pill tone={v.applique_retranscripteur ? 'green' : 'gray'}>{v.applique_retranscripteur ? '✓' : '✕'} Rémunération retranscripteur</Pill>
                </div>
                <p className="small">{libelleConditions(v)}</p>
                <p className="small muted">{periode(v)} · v{v.version}</p>
                {!f.courante && !f.brouillon && (
                  <Alert tone="warning">Désactivée : aucune majoration n'est appliquée. Les valeurs affichées sont indicatives, en attente de confirmation.</Alert>
                )}
                {f.brouillon && gerer && <BrouillonBar v={f.brouillon} onEdit={() => setEdit({ source: f.brouillon })} onAction={actions.go} />}
                <div className="row">
                  {gerer && !f.brouillon && !v.avancee && <button className={`btn ${f.courante ? 'btn-secondary' : 'btn-primary'} btn-sm`} onClick={() => setEdit({ source: v })}>
                    <Pencil size={15} />{f.courante ? 'Modifier' : 'Configurer et activer'}</button>}
                  {gerer && f.courante && <button className="btn btn-ghost btn-sm" onClick={() => {
                    if (window.confirm('Désactiver cette majoration ? Elle ne sera plus appliquée aux nouveaux calculs.')) actions.go(() => api.desactiverGrille(f.courante!.id), 'Majoration désactivée')
                  }}><Power size={15} />Désactiver</button>}
                  <button className="btn btn-ghost btn-sm" onClick={() => setOuvert(ouvert === f.famille_id ? null : f.famille_id)}><History size={15} />Historique</button>
                </div>
                {ouvert === f.famille_id && <Historique f={f} onAction={actions.go} peutGerer={gerer} />}
              </div>
            </section>
          )
        })}
      </div>
      {!data?.length && <div className="card"><Empty icon={<Percent size={24} />} title="Aucune majoration" /></div>}
      {edit && <MajorationEditeur source={edit.source} typesDisponibles={[...disponibles]} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
    </div>
  )
}

/* ── Simulateur ──────────────────────────────────────────────────────────── */
function Simulateur() {
  const clients = useLoad(() => api.clients())
  const prestas = useLoad(() => api.prestataires())
  const [f, setF] = useState({ nombre_pages: '15', type_instance: 'CE', client_id: '', prestataire_id: '', date_reference: aujourdhui(),
    date_limite: '', urgence: false, sans_prise_de_note: false, prestation_speciale: false })
  const [res, setRes] = useState<Simulation | null>(null)
  const { busy, error, run } = useAction()
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  const calculer = async () => {
    const r = await run(() => api.simuler({ ...f, client_id: f.client_id || null, prestataire_id: f.prestataire_id || null,
      date_limite: f.date_limite || null }))
    if (r) setRes(r)
  }
  return (
    <div className="split">
      <div className="card card-pad stack">
        <p className="small muted">Testez vos tarifs avant ou après une modification. La simulation n'enregistre rien.</p>
        <div className="form-grid">
          <Field label="Nombre de pages"><input className="input" type="number" min={1} value={f.nombre_pages} onChange={set('nombre_pages')} /></Field>
          <Field label="Type d'instance"><select className="input" value={f.type_instance} onChange={set('type_instance')}>{INSTANCES.map((i) => <option key={i}>{i}</option>)}</select></Field>
          <Field label="Client"><select className="input" value={f.client_id} onChange={set('client_id')}><option value="">Client quelconque</option>
            {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}</select></Field>
          <Field label="Retranscripteur"><select className="input" value={f.prestataire_id} onChange={set('prestataire_id')}><option value="">Grille par défaut</option>
            {prestas.data?.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}</select></Field>
          <Field label="Réception de l'audio" hint="Détermine la version de tarif applicable"><input className="input" type="date" value={f.date_reference} onChange={set('date_reference')} /></Field>
          <Field label="Échéance client (facultatif)"><input className="input" type="date" value={f.date_limite} onChange={set('date_limite')} /></Field>
        </div>
        <label className="checkbox"><input type="checkbox" checked={f.urgence} onChange={(e) => setF({ ...f, urgence: e.target.checked })} />Urgence</label>
        <label className="checkbox"><input type="checkbox" checked={f.sans_prise_de_note} onChange={(e) => setF({ ...f, sans_prise_de_note: e.target.checked })} />Sans prise de notes</label>
        <label className="checkbox"><input type="checkbox" checked={f.prestation_speciale} onChange={(e) => setF({ ...f, prestation_speciale: e.target.checked })} />Prestation particulière</label>
        <button className="btn btn-primary" disabled={busy || !Number(f.nombre_pages)} onClick={calculer}><Calculator size={17} />Simuler</button>
      </div>
      <div className="card card-pad stack">
        <ErrorBox error={error} />
        {!res ? <Empty icon={<ShieldCheck size={24} />} title="Résultat de la simulation">Renseignez les critères puis lancez la simulation.</Empty> : (
          <>
            <dl className="dl">
              <dt>Tarif client</dt><dd className="mono" style={{ fontSize: 20 }}>{fMoney(res.montant_client)}</dd>
              <dt>Rémunération</dt><dd className="mono">{fMoney(res.montant_retranscripteur)}</dd>
              <dt>Marge</dt><dd className="mono">{fMoney(res.marge)}</dd>
              <dt>Grille client</dt><dd>{res.grille_client ?? '—'}</dd>
              <dt>Grille rémunération</dt><dd>{res.grille_retranscripteur ?? '—'}</dd>
              <dt>Majorations</dt><dd>{res.majorations.length ? res.majorations.join(', ') : 'Aucune'}</dd>
            </dl>
            {res.avertissement && <p className="hint">{res.avertissement}</p>}
            <table><tbody>{res.lignes.map((l, i) => (
              <tr key={i}><td className="small">{l.cible === 'CLIENT' ? 'Client' : 'Retranscripteur'} · {l.libelle}</td>
                <td className="small mono" style={{ textAlign: 'right' }}>{fMoney(l.montant)}</td></tr>
            ))}</tbody></table>
          </>
        )}
      </div>
    </div>
  )
}
