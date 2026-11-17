import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { AlarmClock, FolderOpen, Flame, Plus, Search } from 'lucide-react'
import { api, type DossierResume, type ClientFiche } from '@/lib/api'
import { useAuth } from '@/lib/session'
import { fDate, INSTANCES, relative } from '@/lib/format'
import { Empty, ErrorBox, Field, Modal, PageLoader, Pill, StatutPill } from '@/components/ui'
import { useAction, useLoad } from '@/lib/hooks'

const FILTRES = [
  { key: '', label: 'En cours de traitement' },
  { key: 'a_qualifier', label: 'À qualifier' },
  { key: 'a_attribuer', label: 'À attribuer' },
  { key: 'attribue,en_cours', label: 'En retranscription' },
  { key: 'livre,a_relire', label: 'PV à relire' },
  { key: 'correction_demandee', label: 'Corrections' },
  { key: 'a_controler', label: 'À contrôler' },
  { key: 'valide', label: 'Validés' },
  { key: 'bloque', label: 'Bloqués' },
  { key: 'archive', label: 'Archivés' },
]

export function DossierTable({ items, compact }: { items: DossierResume[]; compact?: boolean }) {
  const navigate = useNavigate()
  if (!items.length) {
    return <Empty icon={<FolderOpen size={24} />} title="Aucun dossier">Rien à afficher pour ce filtre.</Empty>
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Dossier</th>
            <th>Client · instance</th>
            <th>Production</th>
            {!compact && <th>Facturation</th>}
            <th>Retranscripteur</th>
            <th>Échéance</th>
          </tr>
        </thead>
        <tbody>
          {items.map((d) => {
            const ech = d.date_limite_rendu ?? d.date_limite
            const rel = relative(ech)
            const actif = !['valide', 'archive'].includes(d.statut_production)
            return (
              <tr key={d.id} className="clickable" onClick={() => navigate(`/dossiers/${d.id}`)}>
                <td>
                  <div style={{ fontWeight: 600 }} className="row">
                    {d.reference}
                    {d.est_urgent && <Pill tone="red"><Flame size={12} />Urgent</Pill>}
                  </div>
                  {d.titre && <div className="small muted ellipsis" style={{ maxWidth: 260 }}>{d.titre}</div>}
                </td>
                <td>
                  <div>{d.client_nom ?? '—'}</div>
                  <div className="small muted">{d.type_instance}{d.date_seance ? ` · séance du ${fDate(d.date_seance)}` : ''}</div>
                </td>
                <td><StatutPill type="production" value={d.statut_production} /></td>
                {!compact && <td><StatutPill type="facturation" value={d.statut_facturation} /></td>}
                <td>{d.retranscripteur?.nom ?? <span className="muted">—</span>}</td>
                <td>
                  {ech ? (
                    <div>
                      <div>{fDate(ech)}</div>
                      {actif && <div className="small" style={{ color: `var(--${rel.tone === 'green' ? 'muted' : rel.tone})` }}>
                        {d.en_retard && <AlarmClock size={12} style={{ verticalAlign: -1, marginRight: 4 }} />}{rel.texte}
                      </div>}
                    </div>
                  ) : <span className="muted">—</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function DossiersPage() {
  const { can } = useAuth()
  const [params, setParams] = useSearchParams()
  const production = params.get('production') ?? ''
  const retard = params.get('retard') === '1'
  const urgent = params.get('urgent') === '1'
  const [q, setQ] = useState(params.get('q') ?? '')
  const [creer, setCreer] = useState(false)

  const list = useLoad(() => api.dossiers({
    production: production || undefined, retard: retard || undefined, urgent: urgent || undefined,
    q: params.get('q') || undefined, archives: production === 'archive' || undefined, limit: 200,
  }), [params.toString()])

  useEffect(() => {
    const t = window.setTimeout(() => {
      if ((params.get('q') ?? '') !== q) {
        const p = new URLSearchParams(params)
        if (q) p.set('q', q); else p.delete('q')
        setParams(p, { replace: true })
      }
    }, 300)
    return () => window.clearTimeout(t)
  }, [q, params, setParams])

  const setFiltre = (key: string, value: string | null) => {
    const p = new URLSearchParams(params)
    if (value) p.set(key, value); else p.delete(key)
    setParams(p)
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Dossiers</h1>
          <p>Suivi de toutes les retranscriptions, de la réception de l'audio à la validation du PV.</p>
        </div>
        {can('dossiers.gerer') && (
          <button className="btn btn-primary" data-tour="dossier-nouveau" onClick={() => setCreer(true)}><Plus size={18} />Nouveau dossier</button>
        )}
      </div>

      <div className="stack" data-tour="dossiers-filtres">
        <div className="chips" role="group" aria-label="Filtrer par étape">
          {FILTRES.map((f) => (
            <button key={f.key} className={`chip${production === f.key && !retard ? ' active' : ''}`}
              onClick={() => { const p = new URLSearchParams(params); p.delete('retard'); if (f.key) p.set('production', f.key); else p.delete('production'); setParams(p) }}>
              {f.label}
            </button>
          ))}
        </div>
        <div className="toolbar">
          <div className="search">
            <Search size={17} />
            <input className="input" placeholder="Rechercher une référence ou un titre" value={q} onChange={(e) => setQ(e.target.value)}
              aria-label="Rechercher" />
          </div>
          <button className={`chip${retard ? ' active' : ''}`} onClick={() => setFiltre('retard', retard ? null : '1')}>
            <AlarmClock size={15} />En retard
          </button>
          <button className={`chip${urgent ? ' active' : ''}`} onClick={() => setFiltre('urgent', urgent ? null : '1')}>
            <Flame size={15} />Urgents
          </button>
          <span className="muted small" style={{ marginLeft: 'auto' }}>{list.data ? `${list.data.total} dossier(s)` : ''}</span>
        </div>
      </div>

      <ErrorBox error={list.error} />
      <div className="card">
        {list.loading && !list.data ? <PageLoader /> : <DossierTable items={list.data?.items ?? []} />}
      </div>

      {creer && <NouveauDossier onClose={() => setCreer(false)} />}
    </div>
  )
}

export function CriteresFields({ value, onChange }: {
  value: { urgence: boolean; sans_prise_de_note: boolean; prestation_speciale: boolean; type_prestation_speciale?: string | null }
  onChange: (v: typeof value) => void
}) {
  return (
    <div className="stack" style={{ gap: 10 }}>
      <label className="checkbox"><input type="checkbox" checked={value.urgence}
        onChange={(e) => onChange({ ...value, urgence: e.target.checked })} />
        <span><strong>Urgence</strong><br /><span className="hint">Majoration urgence appliquée selon la grille en vigueur</span></span></label>
      <label className="checkbox"><input type="checkbox" checked={value.sans_prise_de_note}
        onChange={(e) => onChange({ ...value, sans_prise_de_note: e.target.checked })} />
        <span><strong>Sans prise de notes</strong></span></label>
      <label className="checkbox"><input type="checkbox" checked={value.prestation_speciale}
        onChange={(e) => onChange({ ...value, prestation_speciale: e.target.checked })} />
        <span><strong>Prestation particulière</strong></span></label>
      {value.prestation_speciale && (
        <input className="input" placeholder="Préciser la prestation" value={value.type_prestation_speciale ?? ''}
          onChange={(e) => onChange({ ...value, type_prestation_speciale: e.target.value })} />
      )}
    </div>
  )
}

export function NouveauDossier({ onClose, audioId, audioClientId, audioDuree, audioNom }: {
  onClose: () => void; audioId?: string; audioClientId?: string | null; audioDuree?: number | null; audioNom?: string
}) {
  const navigate = useNavigate()
  const clients = useLoad<ClientFiche[]>(() => api.clients())
  const { busy, error, run } = useAction()
  const [form, setForm] = useState({
    client_id: audioClientId ?? '', type_instance: 'CE', titre: '', date_seance: '', date_limite: '',
    duree_audio_minutes: audioDuree ? String(audioDuree) : '', notes_internes: '',
  })
  const [qualifier, setQualifier] = useState(true)
  const [criteres, setCriteres] = useState({ urgence: false, sans_prise_de_note: false, prestation_speciale: false, type_prestation_speciale: '' as string | null })
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const d = await run(() => api.createDossier({
      client_id: form.client_id, type_instance: form.type_instance, titre: form.titre || null,
      date_seance: form.date_seance || null, date_limite: form.date_limite || null,
      duree_audio_minutes: form.duree_audio_minutes ? Number(form.duree_audio_minutes) : null,
      notes_internes: form.notes_internes || null, audio_id: audioId ?? null,
      criteres_tarif: { ...criteres, type_prestation_speciale: criteres.prestation_speciale ? criteres.type_prestation_speciale : null },
      qualifier,
    }))
    if (d) navigate(`/dossiers/${d.id}`)
  }

  return (
    <Modal title={audioId ? 'Créer la mission depuis cet audio' : 'Nouveau dossier'} onClose={onClose} large
      footer={<>
        <button className="btn btn-secondary" onClick={onClose} type="button">Annuler</button>
        <button className="btn btn-primary" form="nouveau-dossier" disabled={busy || !form.client_id}>
          {busy ? 'Création…' : qualifier ? 'Créer et passer à l’attribution' : 'Créer le dossier'}
        </button>
      </>}>
      <form id="nouveau-dossier" className="stack-lg" onSubmit={submit}>
        <ErrorBox error={error} />
        {audioNom && <div className="callout small">Audio : <strong>{audioNom}</strong></div>}
        <div className="form-grid">
          <Field label="Client">
            <select className="input" value={form.client_id} onChange={set('client_id')} required>
              <option value="">Choisir…</option>
              {clients.data?.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
            </select>
          </Field>
          <Field label="Type d'instance">
            <select className="input" value={form.type_instance} onChange={set('type_instance')}>
              {INSTANCES.map((i) => <option key={i}>{i}</option>)}
            </select>
          </Field>
          <Field label="Titre" full>
            <input className="input" placeholder="Ex. Réunion plénière ordinaire" value={form.titre} onChange={set('titre')} />
          </Field>
          <Field label="Date de la séance"><input className="input" type="date" value={form.date_seance} onChange={set('date_seance')} /></Field>
          <Field label="Échéance client" hint="Laisser vide : calculée depuis la réception de l'audio selon les délais paramétrés"><input className="input" type="date" value={form.date_limite} onChange={set('date_limite')} /></Field>
          <Field label="Durée de l'audio (minutes)">
            <input className="input" type="number" min={0} value={form.duree_audio_minutes} onChange={set('duree_audio_minutes')} />
          </Field>
        </div>
        <div className="card card-pad" style={{ background: 'var(--surface-2)' }}>
          <div className="stack">
            <label className="checkbox"><input type="checkbox" checked={qualifier} onChange={(e) => setQualifier(e.target.checked)} />
              <span><strong>Qualifier maintenant</strong><br /><span className="hint">Le dossier passe directement « à attribuer »</span></span></label>
            {qualifier && <CriteresFields value={criteres} onChange={(v) => setCriteres({ ...v, type_prestation_speciale: v.type_prestation_speciale ?? '' })} />}
          </div>
        </div>
        <Field label="Notes internes" hint="Jamais visibles par les retranscripteurs">
          <textarea className="input" value={form.notes_internes} onChange={set('notes_internes')} />
        </Field>
      </form>
    </Modal>
  )
}

