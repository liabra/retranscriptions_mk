import { useState } from 'react'
import { CalendarCheck, FileClock, Plus, Trash2 } from 'lucide-react'
import { api, type VersionTarif } from '@/lib/api'
import { INSTANCES } from '@/lib/format'
import { aujourdhui, libellesTranches, type TrancheEdit } from '@/lib/tarifs'
import { Alert, ErrorBox, Field, Modal } from '@/components/ui'
import { toast, useAction } from '@/lib/hooks'

type Usage = 'client' | 'retranscripteur'

/** Choix commun à tous les éditeurs : brouillon ou application datée (jamais rétroactive). */
function Application({ publier, setPublier, date, setDate }: {
  publier: boolean; setPublier: (v: boolean) => void; date: string; setDate: (v: string) => void
}) {
  return (
    <div className="card card-pad stack" style={{ background: 'var(--surface-2)', gap: 10 }}>
      <div className="section-title" style={{ fontSize: 15 }}>Mise en application</div>
      <label className="checkbox"><input type="radio" checked={!publier} onChange={() => setPublier(false)} />
        <span><strong className="row" style={{ gap: 6 }}><FileClock size={15} />Enregistrer comme brouillon</strong>
          <span className="hint">Aucun effet sur les calculs tant que le brouillon n'est pas publié.</span></span></label>
      <label className="checkbox"><input type="radio" checked={publier} onChange={() => setPublier(true)} />
        <span><strong className="row" style={{ gap: 6 }}><CalendarCheck size={15} />Appliquer à partir du</strong></span></label>
      {publier && (
        <input className="input" type="date" min={aujourdhui()} value={date} onChange={(e) => setDate(e.target.value)} style={{ maxWidth: 220 }} />
      )}
      <p className="hint">Les dossiers dont l'audio a été reçu avant cette date conservent l'ancien tarif. Les calculs et factures déjà validés ne sont jamais modifiés.</p>
    </div>
  )
}

/* ── Grille à tranches ───────────────────────────────────────────────────── */
export function GrilleEditeur({ usage, source, datePublication, onClose, onDone }: {
  usage: Usage; source: VersionTarif | null; datePublication?: string; onClose: () => void; onDone: () => void
}) {
  const [nom, setNom] = useState(source?.nom ?? '')
  const [description, setDescription] = useState(source?.description ?? '')
  const [application, setApplication] = useState<VersionTarif['application']>(source?.application ?? 'defaut')
  const [instance, setInstance] = useState(source?.type_instance ?? 'CSSCT')
  const [tranches, setTranches] = useState<TrancheEdit[]>(
    source?.tranches?.map((t) => ({ pages_min: String(Number(t.pages_min) === 0 ? 1 : Number(t.pages_min)), mode: t.mode, montant: String(Number(t.montant)) }))
    ?? [{ pages_min: '1', mode: 'forfait', montant: '' }])
  const [publier, setPublier] = useState(!source?.brouillon)
  const [date, setDate] = useState(datePublication ?? aujourdhui())
  const { busy, error, run } = useAction()

  const set = (i: number, k: keyof TrancheEdit, v: string) => setTranches(tranches.map((t, j) => (j === i ? { ...t, [k]: v } as TrancheEdit : t)))
  const valides = tranches.length > 0 && tranches.every((t) => Number(t.pages_min) >= 0 && Number(t.montant) > 0)
    && tranches.some((t) => Number(t.pages_min) <= 1)
  const apercu = libellesTranches(tranches.filter((t) => t.montant !== ''))

  const enregistrer = async () => {
    const corps = {
      nom, description: description || null, application, type_instance: application === 'instance' ? instance : null,
      tranches: tranches.map((t) => ({ pages_min: t.pages_min, mode: t.mode, montant: t.montant })),
    }
    const res = await run(async () => {
      if (!source) {
        const g = await api.creerGrille({ ...corps, usage })
        return publier ? api.publier(g.id, date) : g
      }
      if (source.brouillon) {
        const g = await api.modifierBrouillon(source.id, corps)
        return publier ? api.publier(g.id, date) : g
      }
      return api.reviser(source.id, { ...corps, publier_le: publier ? date : null })
    })
    if (res) { toast(publier ? 'Tarif enregistré et programmé' : 'Brouillon enregistré'); onDone() }
  }

  return (
    <Modal large title={datePublication ? `Nouveau barème — entrée en vigueur le ${datePublication.split('-').reverse().join('/')}` : source ? `Modifier « ${source.nom} »` : usage === 'client' ? 'Nouvelle grille client' : 'Nouvelle grille de rémunération'}
      onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || nom.length < 2 || !valides || (publier && !date)} onClick={enregistrer}>
          {busy ? 'Enregistrement…' : publier ? 'Enregistrer et appliquer' : 'Enregistrer le brouillon'}</button></>}>
      <div className="stack-lg">
        <ErrorBox error={error} />
        {source && !source.brouillon && (
          <Alert tone="info">La version {source.version} reste conservée dans l'historique. Vos modifications créent une nouvelle version.</Alert>
        )}
        <div className="form-grid">
          <Field label="Nom de la grille" full><input className="input" value={nom} onChange={(e) => setNom(e.target.value)} /></Field>
          <div className="field full">
            <span className="label">S'applique</span>
            <div className="chips">
              <button type="button" className={`chip${application === 'defaut' ? ' active' : ''}`} onClick={() => setApplication('defaut')}>
                {usage === 'client' ? 'À tous les clients (par défaut)' : 'À tous les retranscripteurs (par défaut)'}</button>
              <button type="button" className={`chip${application === 'instance' ? ' active' : ''}`} onClick={() => setApplication('instance')}>À un type d'instance</button>
              <button type="button" className={`chip${application === 'attribuee' ? ' active' : ''}`} onClick={() => setApplication('attribuee')}>
                {usage === 'client' ? 'Aux clients choisis' : 'Aux retranscripteurs choisis'}</button>
            </div>
            {application === 'instance' && (
              <select className="input" style={{ maxWidth: 220, marginTop: 8 }} value={instance} onChange={(e) => setInstance(e.target.value)}>
                {INSTANCES.map((i) => <option key={i}>{i}</option>)}
              </select>
            )}
            {application === 'attribuee' && <span className="hint">Attribuez ensuite la grille depuis la fiche {usage === 'client' ? 'du client' : 'du retranscripteur'}.</span>}
          </div>
        </div>

        <div className="stack" style={{ gap: 10 }}>
          <div className="section-title" style={{ fontSize: 15 }}>Tranches de pages</div>
          <div className="table-wrap"><table>
            <thead><tr><th>À partir de</th><th>Tarification</th><th>Montant (€)</th><th /></tr></thead>
            <tbody>{tranches.map((t, i) => (
              <tr key={i}>
                <td><div className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
                  <input className="input" type="number" min={0} step="0.01" style={{ width: 100 }} value={t.pages_min}
                    onChange={(e) => set(i, 'pages_min', e.target.value)} aria-label="Nombre de pages minimum" />
                  <span className="small muted">pages</span></div></td>
                <td><select className="input" value={t.mode} onChange={(e) => set(i, 'mode', e.target.value)} aria-label="Mode">
                  <option value="forfait">Forfait</option><option value="par_page">Prix par page</option></select></td>
                <td><input className="input" type="number" min={0} step="0.01" style={{ width: 120 }} value={t.montant}
                  onChange={(e) => set(i, 'montant', e.target.value)} aria-label="Montant" /></td>
                <td><button type="button" className="btn btn-ghost btn-icon" aria-label="Supprimer la tranche" disabled={tranches.length === 1}
                  onClick={() => setTranches(tranches.filter((_, j) => j !== i))}><Trash2 size={16} /></button></td>
              </tr>
            ))}</tbody>
          </table></div>
          <button type="button" className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start' }}
            onClick={() => setTranches([...tranches, { pages_min: '', mode: 'forfait', montant: '' }])}><Plus size={15} />Ajouter une tranche</button>
          {!tranches.some((t) => Number(t.pages_min) <= 1) && <p className="small" style={{ color: 'var(--amber)' }}>Une tranche doit commencer à 1 page.</p>}
          {apercu.length > 0 && (
            <div className="callout small">
              <strong>Aperçu :</strong>
              <div className="grid-2" style={{ gap: 4, marginTop: 6 }}>{apercu.map((a, i) => <span key={i}>{a.libelle} · <strong>{a.prix}</strong></span>)}</div>
            </div>
          )}
        </div>

        <Field label="Note (facultatif)"><textarea className="input" value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
        <Application publier={publier} setPublier={setPublier} date={date} setDate={setDate} />
      </div>
    </Modal>
  )
}

/* ── Majoration ──────────────────────────────────────────────────────────── */
const NOMS = { urgence: 'Majoration urgence', snp: 'Sans prise de notes', special: 'Prestation particulière' }

export function MajorationEditeur({ source, typesDisponibles, onClose, onDone }: {
  source: VersionTarif | null; typesDisponibles: ('urgence' | 'snp' | 'special')[]; onClose: () => void; onDone: () => void
}) {
  const [type, setType] = useState<'urgence' | 'snp' | 'special'>((source?.type as 'urgence') ?? typesDisponibles[0] ?? 'urgence')
  const [nom, setNom] = useState(source?.nom ?? NOMS[type])
  const [mode, setMode] = useState<'pourcentage' | 'montant'>(source?.majoration?.mode ?? 'pourcentage')
  const [valeur, setValeur] = useState(source?.majoration ? String(Number(source.majoration.valeur)) : '')
  const [client, setClient] = useState(source?.applique_client ?? true)
  const [retrans, setRetrans] = useState(source?.applique_retranscripteur ?? false)
  const c = source?.conditions ?? { case_cochee: true, dossier_signale_urgent: true, delai_max_jours: null }
  const [caseCochee, setCaseCochee] = useState(c.case_cochee)
  const [signale, setSignale] = useState(c.dossier_signale_urgent)
  const [delaiOn, setDelaiOn] = useState(c.delai_max_jours !== null)
  const [delai, setDelai] = useState(String(c.delai_max_jours ?? 2))
  const [publier, setPublier] = useState(!source?.brouillon)
  const [date, setDate] = useState(aujourdhui())
  const { busy, error, run } = useAction()

  const corps = {
    nom, mode, valeur, applique_client: client, applique_retranscripteur: retrans,
    conditions: type === 'urgence' ? { case_cochee: caseCochee, dossier_signale_urgent: signale, delai_max_jours: delaiOn ? Number(delai) : null } : null,
  }
  const valide = nom.length >= 2 && Number(valeur) > 0 && (client || retrans) && !(mode === 'pourcentage' && Number(valeur) > 300)

  const enregistrer = async () => {
    const res = await run(async () => {
      if (!source) {
        const g = await api.creerMajoration({ ...corps, type })
        return publier ? api.publier(g.id, date) : g
      }
      if (source.brouillon) {
        const g = await api.modifierBrouillon(source.id, corps)
        return publier ? api.publier(g.id, date) : g
      }
      return api.reviser(source.id, { ...corps, publier_le: publier ? date : null })
    })
    if (res) { toast('Majoration enregistrée'); onDone() }
  }

  return (
    <Modal title={source ? `Modifier « ${source.nom} »` : 'Nouvelle majoration'} onClose={onClose} large
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || !valide || (publier && !date)} onClick={enregistrer}>
          {busy ? 'Enregistrement…' : publier ? 'Enregistrer et appliquer' : 'Enregistrer le brouillon'}</button></>}>
      <div className="stack-lg">
        <ErrorBox error={error} />
        {source && !source.brouillon && <Alert tone="info">La configuration actuelle reste conservée dans l'historique.</Alert>}
        <div className="form-grid">
          {!source && (
            <Field label="Type">
              <select className="input" value={type} onChange={(e) => { const t = e.target.value as typeof type; setType(t); setNom(NOMS[t]) }}>
                {typesDisponibles.map((t) => <option key={t} value={t}>{NOMS[t]}</option>)}
              </select>
            </Field>
          )}
          <Field label="Nom"><input className="input" value={nom} onChange={(e) => setNom(e.target.value)} /></Field>
          <div className="field full">
            <span className="label">Majoration</span>
            <div className="row">
              <div className="chips">
                <button type="button" className={`chip${mode === 'pourcentage' ? ' active' : ''}`} onClick={() => setMode('pourcentage')}>Pourcentage</button>
                <button type="button" className={`chip${mode === 'montant' ? ' active' : ''}`} onClick={() => setMode('montant')}>Montant fixe</button>
              </div>
              <div className="row" style={{ gap: 6 }}>
                <input className="input" type="number" min={0} step="0.01" style={{ width: 120 }} value={valeur}
                  onChange={(e) => setValeur(e.target.value)} aria-label="Valeur" />
                <span className="muted">{mode === 'pourcentage' ? '% du tarif de base' : '€ par dossier'}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="stack" style={{ gap: 10 }}>
          <div className="section-title" style={{ fontSize: 15 }}>S'applique à</div>
          <label className="checkbox"><input type="checkbox" checked={client} onChange={(e) => setClient(e.target.checked)} />
            <span><strong>Tarif facturé au client</strong></span></label>
          <label className="checkbox"><input type="checkbox" checked={retrans} onChange={(e) => setRetrans(e.target.checked)} />
            <span><strong>Rémunération du retranscripteur</strong><br /><span className="hint">Calculée sur sa propre grille de rémunération</span></span></label>
          {!client && !retrans && <p className="small" style={{ color: 'var(--red)' }}>Choisissez au moins une application.</p>}
        </div>

        {type === 'urgence' && (
          <div className="stack" style={{ gap: 10 }}>
            <div className="section-title" style={{ fontSize: 15 }}>Se déclenche</div>
            <label className="checkbox"><input type="checkbox" checked={caseCochee} onChange={(e) => setCaseCochee(e.target.checked)} />
              <span>Quand la case « Urgence » est cochée lors de la qualification</span></label>
            <label className="checkbox"><input type="checkbox" checked={signale} onChange={(e) => setSignale(e.target.checked)} />
              <span>Quand le dossier est signalé urgent<br /><span className="hint">Échéance client à moins de 2 jours à la création, ou marqué urgent par une responsable</span></span></label>
            <label className="checkbox"><input type="checkbox" checked={delaiOn} onChange={(e) => setDelaiOn(e.target.checked)} />
              <span>Automatiquement si le délai entre la réception de l'audio et l'échéance client est de</span></label>
            {delaiOn && <div className="row" style={{ gap: 6, marginLeft: 27 }}>
              <input className="input" type="number" min={0} max={90} style={{ width: 90 }} value={delai} onChange={(e) => setDelai(e.target.value)} aria-label="Délai" />
              <span className="muted">jour(s) ou moins</span></div>}
          </div>
        )}
        {type === 'snp' && <p className="hint">Se déclenche quand « Sans prise de notes » est coché sur le dossier.</p>}
        {type === 'special' && <p className="hint">Se déclenche quand « Prestation particulière » est cochée sur le dossier.</p>}

        <Application publier={publier} setPublier={setPublier} date={date} setDate={setDate} />
      </div>
    </Modal>
  )
}
