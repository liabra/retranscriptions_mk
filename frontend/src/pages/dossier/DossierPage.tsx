import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Archive, ArrowLeft, AudioLines, CalendarClock, CheckCircle2, Download, Flame, Lock, MessageSquareWarning,
  PencilLine, PlayCircle, Unlock, UserMinus, type LucideIcon,
} from 'lucide-react'
import { api, type DossierDetail } from '@/lib/api'
import { downloadFile } from '@/services/api'
import { useAuth } from '@/lib/session'
import { ETAPES, etapeIndex, fDate, fDateTime, fDuree, fSize, relative } from '@/lib/format'
import { Alert, ErrorBox, Field, Modal, PageLoader, Pill, StatutPill, Tabs } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'
import { CriteresFields } from '@/pages/DossiersPage'
import { Versions } from './Versions'
import { Attribution } from './Attribution'
import { Finance } from './Finance'

type Onglet = 'apercu' | 'versions' | 'attribution' | 'finance' | 'historique'

export function DossierPage() {
  const { id = '' } = useParams()
  const { can } = useAuth()
  const { data: d, error, loading, reload } = useLoad(() => api.dossier(id), [id])
  const [onglet, setOnglet] = useState<Onglet>('apercu')

  if (loading && !d) return <PageLoader />
  if (!d) return <ErrorBox error={error} />

  const tabs: { key: Onglet; label: string; count?: number | null }[] = [
    { key: 'apercu', label: 'Aperçu' },
    { key: 'versions', label: 'Versions du PV', count: d.livraisons.length || null },
    { key: 'attribution', label: 'Attribution' },
  ]
  if (d.acces_finance) tabs.push({ key: 'finance', label: 'Facturation' })
  if (can('journal.voir')) tabs.push({ key: 'historique', label: 'Historique' })

  return (
    <div className="page">
      <div>
        <Link to="/dossiers" className="small row" style={{ gap: 6 }}><ArrowLeft size={15} />Dossiers</Link>
        <div className="page-head" style={{ alignItems: 'flex-start' }}>
          <div>
            <div className="row">
              <h1>{d.reference}</h1>
              {d.est_urgent && <Pill tone="red"><Flame size={13} />Urgent</Pill>}
              {d.en_retard && <Pill tone="red">En retard</Pill>}
            </div>
            <p>{d.titre ?? 'Sans titre'} · {d.client_nom} · {d.type_instance}{d.date_seance ? ` · séance du ${fDate(d.date_seance)}` : ''}</p>
          </div>
          <div className="row">
            <StatutPill type="production" value={d.statut_production} />
            <StatutPill type="facturation" value={d.statut_facturation} />
          </div>
        </div>
      </div>

      {d.statut_production === 'bloque' && (
        <Alert tone="error"><strong>Dossier bloqué</strong> — {d.motif_blocage}</Alert>
      )}

      <div className="card card-pad">
        <div className="steps" aria-label="Avancement">
          {ETAPES.map((e, i) => {
            const idx = etapeIndex(d.statut_production)
            const cls = d.statut_production === 'archive' || i < idx ? 'done' : i === idx ? 'current' : ''
            return (
              <div key={e.key} className={`step ${cls}`}>
                <span className="step-dot">{cls === 'done' ? <CheckCircle2 size={15} /> : i + 1}</span>
                {e.label}
              </div>
            )
          })}
        </div>
      </div>

      <ProchaineAction d={d} onChange={reload} goTo={setOnglet} />

      <Tabs value={onglet} onChange={setOnglet} items={tabs} />
      {onglet === 'apercu' && <Apercu d={d} onChange={reload} />}
      {onglet === 'versions' && <Versions dossier={d} onChange={reload} />}
      {onglet === 'attribution' && <Attribution dossier={d} onChange={reload} />}
      {onglet === 'finance' && <Finance dossier={d} onChange={reload} />}
      {onglet === 'historique' && <Historique id={d.id} />}
    </div>
  )
}

function ActionCard({ icon: Icon, tone, title, text, children }: {
  icon: LucideIcon; tone: string; title: string; text: string; children?: React.ReactNode
}) {
  return (
    <div className="card card-pad" style={{ borderLeft: `4px solid var(--${tone === 'primary' ? 'primary' : tone})` }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="row" style={{ alignItems: 'flex-start', flex: 1, minWidth: 260 }}>
          <span className={`kpi-icon tone-${tone}`}><Icon size={18} /></span>
          <div>
            <div className="eyebrow">Prochaine étape</div>
            <div style={{ fontWeight: 600, fontSize: 16 }}>{title}</div>
            <div className="small muted">{text}</div>
          </div>
        </div>
        <div className="row">{children}</div>
      </div>
    </div>
  )
}

function ProchaineAction({ d, onChange, goTo }: { d: DossierDetail; onChange: () => void; goTo: (o: Onglet) => void }) {
  const { can } = useAuth()
  const action = useAction()
  const [modal, setModal] = useState<'qualifier' | 'correction' | 'valider' | 'retirer' | 'echeance' | null>(null)
  const aff = d.affectations.find((a) => ['en_attente', 'en_cours', 'livre'].includes(a.statut))
  const go = (fn: () => Promise<unknown>, msg: string) =>
    action.run(async () => { await fn(); toast(msg); onChange() })

  let card: React.ReactNode = null
  switch (d.statut_production) {
    case 'a_qualifier':
      card = <ActionCard icon={PencilLine} tone="gray" title="Qualifier le dossier" text="Renseignez l'échéance et les critères de tarification.">
        {can('dossiers.gerer') && <button className="btn btn-primary" onClick={() => setModal('qualifier')}>Qualifier</button>}
      </ActionCard>
      break
    case 'a_attribuer':
      card = <ActionCard icon={UserMinus} tone="amber" title="Attribuer la mission" text={d.audio?.disponible ? 'Consultez les suggestions et choisissez un retranscripteur.' : 'Aucun audio vérifié n’est associé : le retranscripteur ne pourra pas le télécharger.'}>
        {can('attribution.gerer') && <button className="btn btn-primary" onClick={() => goTo('attribution')}>Choisir un retranscripteur</button>}
      </ActionCard>
      break
    case 'attribue':
    case 'en_cours':
    case 'correction_demandee': {
      const rel = relative(aff?.date_limite_rendu)
      card = <ActionCard icon={PlayCircle} tone="blue"
        title={d.statut_production === 'correction_demandee' ? `Correction en cours — ${aff?.prestataire_nom}` : `Retranscription par ${aff?.prestataire_nom}`}
        text={`Échéance : ${fDate(aff?.date_limite_rendu)} · ${rel.texte}`}>
        {can('attribution.gerer') && aff && <>
          <button className="btn btn-secondary btn-sm" onClick={() => setModal('echeance')}><CalendarClock size={16} />Échéance</button>
          <button className="btn btn-danger btn-sm" onClick={() => setModal('retirer')}><UserMinus size={16} />Retirer</button>
        </>}
      </ActionCard>
      break
    }
    case 'livre':
      card = <ActionCard icon={MessageSquareWarning} tone="violet" title="PV reçu" text="Prenez en charge la relecture pour contrôler le document.">
        {can('relecture') && <button className="btn btn-primary" disabled={action.busy}
          onClick={() => go(() => api.commencerRelecture(d.id), 'Relecture commencée')}>Commencer la relecture</button>}
      </ActionCard>
      break
    case 'a_relire':
      card = <ActionCard icon={PencilLine} tone="violet" title="Relecture en cours" text="Demandez une correction au retranscripteur, déposez votre version corrigée, puis terminez la relecture.">
        {can('relecture') && <>
          <button className="btn btn-secondary" onClick={() => setModal('correction')}>Demander une correction</button>
          <button className="btn btn-primary" disabled={action.busy} onClick={() => go(() => api.terminerRelecture(d.id), 'Relecture terminée')}>Terminer la relecture</button>
        </>}
      </ActionCard>
      break
    case 'a_controler':
      card = <ActionCard icon={CheckCircle2} tone="green" title="Contrôle final" text="Vérifiez la dernière version puis validez le PV.">
        {can('relecture') && <button className="btn btn-secondary" onClick={() => setModal('correction')}>Demander une correction</button>}
        {can('validation') && <button className="btn btn-primary" onClick={() => setModal('valider')}>Valider le PV</button>}
      </ActionCard>
      break
    case 'valide':
      card = <ActionCard icon={CheckCircle2} tone="green" title="PV validé" text={`Validé le ${fDate(d.valide_le)} · ${d.nombre_pages_final ?? '—'} pages.`}>
        {d.acces_finance && <button className="btn btn-secondary" onClick={() => goTo('finance')}>Facturation</button>}
        {can('dossiers.gerer') && <button className="btn btn-ghost" disabled={action.busy} onClick={() => go(() => api.archiver(d.id), 'Dossier archivé')}><Archive size={16} />Archiver</button>}
      </ActionCard>
      break
    case 'bloque':
      card = can('dossiers.gerer') ? <ActionCard icon={Lock} tone="red" title="Dossier bloqué" text="Débloquez le dossier pour reprendre à l'étape précédente.">
        <button className="btn btn-primary" onClick={() => go(() => api.debloquer(d.id), 'Dossier débloqué')}><Unlock size={16} />Débloquer</button>
      </ActionCard> : null
      break
  }

  return (
    <>
      <ErrorBox error={action.error} />
      {card}
      {modal === 'qualifier' && <Qualifier d={d} onClose={() => setModal(null)} onDone={() => { setModal(null); onChange() }} />}
      {modal === 'correction' && <DemandeCorrection d={d} onClose={() => setModal(null)} onDone={() => { setModal(null); onChange() }} />}
      {modal === 'valider' && <Valider d={d} onClose={() => setModal(null)} onDone={() => { setModal(null); onChange() }} />}
      {modal === 'retirer' && aff && <Retirer affId={aff.id} nom={aff.prestataire_nom} onClose={() => setModal(null)} onDone={() => { setModal(null); onChange() }} />}
      {modal === 'echeance' && aff && <Echeance affId={aff.id} actuelle={aff.date_limite_rendu} onClose={() => setModal(null)} onDone={() => { setModal(null); onChange() }} />}
    </>
  )
}

function Qualifier({ d, onClose, onDone }: { d: DossierDetail; onClose: () => void; onDone: () => void }) {
  const [criteres, setCriteres] = useState({ urgence: false, sans_prise_de_note: false, prestation_speciale: false, type_prestation_speciale: '' as string | null, ...(d.criteres_tarif ?? {}) })
  const [dateLimite, setDateLimite] = useState(d.date_limite ?? '')
  const [duree, setDuree] = useState(d.duree_audio_minutes ? String(d.duree_audio_minutes) : '')
  const { busy, error, run } = useAction()
  return (
    <Modal title="Qualifier le dossier" onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy} onClick={async () => {
          if (await run(() => api.qualifier(d.id, { criteres_tarif: { ...criteres, type_prestation_speciale: criteres.prestation_speciale ? criteres.type_prestation_speciale : null }, date_limite: dateLimite && dateLimite !== d.date_limite ? dateLimite : null, duree_audio_minutes: duree ? Number(duree) : null }))) { toast('Dossier qualifié'); onDone() }
        }}>Qualifier</button></>}>
      <div className="stack-lg">
        <ErrorBox error={error} />
        <div className="form-grid">
          <Field label="Échéance client"><input className="input" type="date" value={dateLimite} onChange={(e) => setDateLimite(e.target.value)} /></Field>
          <Field label="Durée audio (minutes)"><input className="input" type="number" value={duree} onChange={(e) => setDuree(e.target.value)} /></Field>
        </div>
        <CriteresFields value={criteres} onChange={(v) => setCriteres({ ...criteres, ...v })} />
      </div>
    </Modal>
  )
}

function DemandeCorrection({ d, onClose, onDone }: { d: DossierDetail; onClose: () => void; onDone: () => void }) {
  const [message, setMessage] = useState('')
  const [echeance, setEcheance] = useState('')
  const { busy, error, run } = useAction()
  const derniere = d.livraisons[0]
  return (
    <Modal title="Demander une correction" onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || message.trim().length < 5} onClick={async () => {
          if (await run(() => api.demanderCorrection(d.id, { message, livraison_id: derniere?.id, date_limite: echeance ? new Date(`${echeance}T18:00:00`).toISOString() : null }))) { toast('Demande envoyée au retranscripteur'); onDone() }
        }}>Envoyer la demande</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        {derniere && <p className="small muted">Concerne la version {derniere.version} ({derniere.nom_original}).</p>}
        <Field label="Corrections attendues" hint="Ce message est transmis au retranscripteur">
          <textarea className="input" rows={6} value={message} onChange={(e) => setMessage(e.target.value)}
            placeholder="Ex. Appliquer Comic Sans MS 12 sur tout le document, compléter l'intervention de M. X page 4…" />
        </Field>
        <Field label="Nouvelle échéance (facultatif)"><input className="input" type="date" value={echeance} onChange={(e) => setEcheance(e.target.value)} /></Field>
      </div>
    </Modal>
  )
}

function Valider({ d, onClose, onDone }: { d: DossierDetail; onClose: () => void; onDone: () => void }) {
  const [livraisonId, setLivraisonId] = useState(d.livraisons[0]?.id ?? '')
  const liv = d.livraisons.find((l) => l.id === livraisonId)
  const [pages, setPages] = useState(liv?.pages_declarees ? String(liv.pages_declarees) : '')
  const [derogation, setDerogation] = useState('')
  const { busy, error, run } = useAction()
  const nonConforme = liv?.statut_controle === 'non_conforme'
  return (
    <Modal title="Valider le PV" onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || !livraisonId || !Number(pages) || (nonConforme && derogation.trim().length < 3)} onClick={async () => {
          if (await run(() => api.valider(d.id, { livraison_id: livraisonId, nombre_pages_final: pages, derogation_motif: derogation || null }))) { toast('PV validé'); onDone() }
        }}><CheckCircle2 size={17} />Valider définitivement</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        <Field label="Version validée">
          <select className="input" value={livraisonId} onChange={(e) => setLivraisonId(e.target.value)}>
            {d.livraisons.map((l) => <option key={l.id} value={l.id}>Version {l.version} — {l.statut_controle === 'non_conforme' ? 'non conforme' : 'conforme'} — {fDateTime(l.depose_le)}</option>)}
          </select>
        </Field>
        <Field label="Nombre de pages du PV final" hint={liv?.pages_declarees ? `Word indique ${liv.pages_declarees} pages pour ce document` : 'Sert de base au calcul tarifaire'}>
          <input className="input" type="number" min={1} step="1" value={pages} onChange={(e) => setPages(e.target.value)} />
        </Field>
        {nonConforme && (
          <>
            <Alert tone="warning">Cette version ne respecte pas la mise en forme requise. Indiquez pourquoi vous la validez malgré tout.</Alert>
            <Field label="Motif de dérogation"><input className="input" value={derogation} onChange={(e) => setDerogation(e.target.value)} /></Field>
          </>
        )}
        <p className="small muted">Après validation, le retranscripteur est informé et la facture devient « à établir ».</p>
      </div>
    </Modal>
  )
}

function Retirer({ affId, nom, onClose, onDone }: { affId: string; nom: string | null; onClose: () => void; onDone: () => void }) {
  const [motif, setMotif] = useState('')
  const { busy, error, run } = useAction()
  return (
    <Modal title={`Retirer la mission à ${nom}`} onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-danger" disabled={busy || motif.length < 3} onClick={async () => { if (await run(() => api.retirer(affId, motif))) { toast('Mission retirée'); onDone() } }}>Retirer</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        <p className="small muted">Le retranscripteur perd immédiatement l'accès à l'audio. Le dossier repasse « à attribuer ».</p>
        <Field label="Motif"><input className="input" value={motif} onChange={(e) => setMotif(e.target.value)} /></Field>
      </div>
    </Modal>
  )
}

function Echeance({ affId, actuelle, onClose, onDone }: { affId: string; actuelle: string | null; onClose: () => void; onDone: () => void }) {
  const [date, setDate] = useState(actuelle ? actuelle.slice(0, 10) : '')
  const { busy, error, run } = useAction()
  return (
    <Modal title="Modifier l'échéance de rendu" onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || !date} onClick={async () => {
          if (await run(() => api.modifierAffectation(affId, { date_limite_rendu: new Date(`${date}T18:00:00`).toISOString() }))) { toast('Échéance mise à jour'); onDone() }
        }}>Enregistrer</button></>}>
      <ErrorBox error={error} />
      <Field label="Nouvelle échéance"><input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
    </Modal>
  )
}

function Apercu({ d, onChange }: { d: DossierDetail; onChange: () => void }) {
  const { can } = useAuth()
  const action = useAction()
  const [edit, setEdit] = useState(false)
  const navigate = useNavigate()
  const a = d.audio
  return (
    <div className="split">
      <div className="stack-lg">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Informations</h3>
            {can('dossiers.gerer') && d.statut_production !== 'archive' && <button className="btn btn-ghost btn-sm" onClick={() => setEdit(true)}><PencilLine size={15} />Modifier</button>}
          </div>
          <div className="card-body">
            <dl className="dl">
              <dt>Client</dt><dd>{d.client_nom}</dd>
              <dt>Payeur</dt><dd>{d.payeur_nom ?? d.client_nom}</dd>
              <dt>Instance</dt><dd>{d.type_instance}</dd>
              <dt>Séance</dt><dd>{fDate(d.date_seance)}</dd>
              <dt>Audio reçu le</dt><dd>{fDate(d.date_reception_audio)}</dd>
              <dt>Échéance client</dt><dd>
                {fDate(d.date_limite)}{' '}
                <span className="small muted">
                  {d.echeance_mode === 'calculee'
                    ? (d.echeance_detail?.regle
                      ? `· calculée : ${d.echeance_detail.delai_jours} j ${d.echeance_detail.type_jours === 'ouvres' ? 'ouvrés ' : ''}après réception (« ${d.echeance_detail.regle} »)`
                      : '· aucune règle de délai applicable : à saisir')
                    : '· saisie manuellement'}
                  {d.echeance_figee_le
                    ? ` · figée le ${fDate(d.echeance_figee_le)} à l'attribution`
                    : d.echeance_mode === 'calculee' ? ' · prévisionnelle, suit les règles jusqu’à l’attribution' : ''}
                  {d.echeance_mode === 'manuelle' && !d.echeance_figee_le && can('dossiers.gerer') && ['a_qualifier', 'a_attribuer'].includes(d.statut_production) && (
                    <> · <a role="button" style={{ cursor: 'pointer' }} onClick={() => action.run(async () => { await api.recalculerEcheance(d.id); toast('Échéance recalculée'); onChange() })}>utiliser le délai paramétré</a></>)}
                </span>
              </dd>
              <dt>Durée</dt><dd>{fDuree(d.duree_audio_minutes)}</dd>
              <dt>Confidentialité</dt><dd>{{ standard: 'Standard', renforce: 'Renforcée', absolu: 'Absolue' }[d.niveau_confidentialite] ?? d.niveau_confidentialite}</dd>
              <dt>Tarification</dt><dd className="row" style={{ gap: 6 }}>
                {!d.criteres_tarif ? <span className="muted">Non qualifié</span> : <>
                  {d.criteres_tarif.urgence && <Pill tone="red">Urgence</Pill>}
                  {d.criteres_tarif.sans_prise_de_note && <Pill tone="blue">Sans prise de notes</Pill>}
                  {d.criteres_tarif.prestation_speciale && <Pill tone="violet">{d.criteres_tarif.type_prestation_speciale || 'Prestation particulière'}</Pill>}
                  {!d.criteres_tarif.urgence && !d.criteres_tarif.sans_prise_de_note && !d.criteres_tarif.prestation_speciale && 'Standard'}
                </>}
              </dd>
            </dl>
          </div>
        </div>
        {d.notes_internes && (
          <div className="card card-pad">
            <div className="eyebrow" style={{ color: 'var(--muted)' }}>Notes internes · non visibles des retranscripteurs</div>
            <p style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{d.notes_internes}</p>
          </div>
        )}
      </div>
      <div className="stack-lg">
        <div className="card">
          <div className="card-header"><h3 className="card-title row"><AudioLines size={18} />Audio original</h3></div>
          <div className="card-body stack">
            <ErrorBox error={action.error} />
            {!a ? <p className="muted small">Aucun audio associé. <Link to="/audios">Associer un audio</Link></p> : (
              <>
                <div style={{ fontWeight: 600 }} className="ellipsis">{a.nom_fichier}</div>
                <div className="small muted">{fSize(a.taille_octets)} · {fDuree(a.duree_minutes)}</div>
                <Pill tone={a.disponible ? 'green' : 'amber'} dot>{a.disponible ? 'Disponible pour le retranscripteur' : 'Non vérifié'}</Pill>
                {a.message_verification && !a.disponible && <p className="small muted">{a.message_verification}</p>}
                {a.disponible && (can('audios.gerer') || can('relecture')) && (
                  <button className="btn btn-secondary btn-sm" disabled={action.busy}
                    onClick={() => action.run(() => downloadFile(`/audios/${a.id}/fichier`, a.nom_fichier))}>
                    <Download size={15} />Télécharger
                  </button>
                )}
                <p className="hint">Le lien OneDrive n'est jamais transmis : les fichiers passent par la plateforme.</p>
              </>
            )}
          </div>
        </div>
        {can('dossiers.gerer') && (
          <div className="card card-pad stack">
            <div className="small" style={{ fontWeight: 600 }}>Autres actions</div>
            <button className="btn btn-secondary btn-sm" disabled={action.busy}
              onClick={() => action.run(async () => { await api.urgence(d.id, !d.est_urgent); onChange() })}>
              <Flame size={15} />{d.est_urgent ? 'Retirer l’urgence' : 'Marquer urgent'}
            </button>
            {d.statut_production !== 'bloque' && !['valide', 'archive'].includes(d.statut_production) && (
              <button className="btn btn-secondary btn-sm" onClick={() => {
                const motif = window.prompt('Motif du blocage (visible dans l’historique) :')
                if (motif && motif.trim().length >= 3) action.run(async () => { await api.bloquer(d.id, motif.trim()); onChange() })
              }}><Lock size={15} />Bloquer le dossier</button>
            )}
            {['a_qualifier', 'a_attribuer'].includes(d.statut_production) && (
              <button className="btn btn-danger btn-sm" onClick={() => {
                if (window.confirm('Supprimer ce dossier ? Il restera dans le journal d’activité.')) {
                  action.run(async () => { await api.supprimerDossier(d.id); navigate('/dossiers') })
                }
              }}>Supprimer</button>
            )}
          </div>
        )}
      </div>
      {edit && <Modifier d={d} onClose={() => setEdit(false)} onDone={() => { setEdit(false); onChange() }} />}
    </div>
  )
}

function Modifier({ d, onClose, onDone }: { d: DossierDetail; onClose: () => void; onDone: () => void }) {
  const [form, setForm] = useState({ titre: d.titre ?? '', date_seance: d.date_seance ?? '', date_limite: d.date_limite ?? '',
    duree_audio_minutes: d.duree_audio_minutes ? String(d.duree_audio_minutes) : '', notes_internes: d.notes_internes ?? '',
    niveau_confidentialite: d.niveau_confidentialite })
  const { busy, error, run } = useAction()
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })
  return (
    <Modal title="Modifier le dossier" onClose={onClose} large
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy} onClick={async () => {
          const { date_limite, ...reste } = form
          const body: Record<string, unknown> = { ...reste, date_seance: form.date_seance || null,
            duree_audio_minutes: form.duree_audio_minutes ? Number(form.duree_audio_minutes) : null }
          if (date_limite !== (d.date_limite ?? '')) body.date_limite = date_limite || null  // vide = retour au calcul
          if (await run(() => api.updateDossier(d.id, body))) onDone()
        }}>Enregistrer</button></>}>
      <ErrorBox error={error} />
      <div className="form-grid">
        <Field label="Titre" full><input className="input" value={form.titre} onChange={set('titre')} /></Field>
        <Field label="Date de séance"><input className="input" type="date" value={form.date_seance} onChange={set('date_seance')} /></Field>
        <Field label="Échéance client" hint={d.echeance_figee_le ? "Échéance figée depuis l'attribution : toute modification est historisée (ancienne et nouvelle date, auteur)" : "Vider le champ pour revenir à l'échéance calculée"}><input className="input" type="date" value={form.date_limite} onChange={set('date_limite')} /></Field>
        <Field label="Durée (minutes)"><input className="input" type="number" value={form.duree_audio_minutes} onChange={set('duree_audio_minutes')} /></Field>
        <Field label="Confidentialité"><select className="input" value={form.niveau_confidentialite} onChange={set('niveau_confidentialite')}>
          <option value="standard">Standard</option><option value="renforce">Renforcée</option><option value="absolu">Absolue</option></select></Field>
        <Field label="Notes internes" full><textarea className="input" value={form.notes_internes} onChange={set('notes_internes')} /></Field>
      </div>
    </Modal>
  )
}

const ACTIONS: Record<string, string> = {
  creation: 'Création', statut: 'Changement d’étape', affectation: 'Attribution', paiement: 'Facturation',
  ajustement_tarifaire: 'Ajustement tarifaire', note: 'Modification', calcul_tarifaire: 'Calcul tarifaire',
  acces_document: 'Document', archivage: 'Archivage', auth: 'Compte',
}

function Historique({ id }: { id: string }) {
  const { data, error, loading } = useLoad(() => api.journal(id), [id])
  if (loading && !data) return <PageLoader />
  return (
    <div className="card">
      <ErrorBox error={error} />
      <div className="list">
        {data?.map((e) => {
          const det = e.detail ?? {}
          const resume = [det.action, det.ancien && det.nouveau ? `${det.ancien} → ${det.nouveau}` : null, det.motif, det.version ? `v${det.version}` : null]
            .filter(Boolean).join(' · ')
          return (
            <div key={e.id} className="list-item">
              <div className="list-main">
                <div className="list-title">{ACTIONS[e.type_action.toLowerCase()] ?? e.type_action}</div>
                <div className="small muted">{String(resume).replace(/_/g, ' ')}</div>
              </div>
              <div className="small muted" style={{ textAlign: 'right' }}>{e.utilisateur_nom ?? 'Système'}<br />{fDateTime(e.timestamp)}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
