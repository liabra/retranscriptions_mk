import { useState } from 'react'
import { Building2, KeyRound, Plus, Users } from 'lucide-react'
import { api, type ClientFiche, type PrestataireFiche } from '@/lib/api'
import { useAuth } from '@/lib/session'
import { fDate, INSTANCES } from '@/lib/format'
import { Alert, Empty, ErrorBox, Field, Modal, PageLoader, Pill } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'

/* ── Clients ─────────────────────────────────────────────────────────────── */
export function ClientsPage() {
  const { can } = useAuth()
  const [inactifs, setInactifs] = useState(false)
  const { data, error, loading, reload } = useLoad(() => api.clients(!inactifs), [inactifs])
  const [edit, setEdit] = useState<ClientFiche | 'new' | null>(null)
  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Clients & instances</h1><p>CSE, CMAS, CSSCT et autres instances pour lesquelles A2C réalise des retranscriptions.</p></div>
        {can('clients.gerer') && <button className="btn btn-primary" onClick={() => setEdit('new')}><Plus size={18} />Nouveau client</button>}
      </div>
      <label className="checkbox"><input type="checkbox" checked={inactifs} onChange={(e) => setInactifs(e.target.checked)} />Afficher les clients inactifs</label>
      <ErrorBox error={error} />
      <div className="card">
        {loading && !data ? <PageLoader /> : !data?.length ? <Empty icon={<Building2 size={24} />} title="Aucun client" /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Nom</th><th>Type</th><th>Contact</th><th>Paiement</th><th /></tr></thead>
            <tbody>{data.map((c) => (
              <tr key={c.id}>
                <td><strong>{c.nom}</strong>{c.entreprise_mere && <div className="small muted">{c.entreprise_mere}</div>}</td>
                <td><Pill tone="primary">{c.type}</Pill> {!c.actif && <Pill>Inactif</Pill>}</td>
                <td>{c.contact_principal ?? '—'}<div className="small muted">{c.email_contact}</div></td>
                <td className="small">{c.conditions_paiement ?? '—'}</td>
                <td style={{ textAlign: 'right' }}>{can('clients.gerer') && <button className="btn btn-ghost btn-sm" onClick={() => setEdit(c)}>Modifier</button>}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
      {edit && <ClientForm client={edit === 'new' ? null : edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
    </div>
  )
}

function ClientForm({ client, onClose, onDone }: { client: ClientFiche | null; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({
    nom: client?.nom ?? '', type: client?.type ?? 'CE', entreprise_mere: client?.entreprise_mere ?? '',
    contact_principal: client?.contact_principal ?? '', email_contact: client?.email_contact ?? '',
    telephone: client?.telephone ?? '', conditions_paiement: client?.conditions_paiement ?? '', actif: client?.actif ?? true,
    grille_tarifaire_id: client?.grille_tarifaire_id ?? '',
  })
  const { can } = useAuth()
  const grilles = useLoad(() => can('tarifs.gerer') || can('finance.voir') ? api.catalogue('client') : Promise.resolve([]))
  const attribuables = (grilles.data ?? []).filter((g) => g.courante && g.courante.application === 'attribuee')
  const { busy, error, run } = useAction()
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  const save = async () => {
    const body = { ...f, email_contact: f.email_contact || null, entreprise_mere: f.entreprise_mere || null,
      grille_tarifaire_id: f.grille_tarifaire_id || null }
    if (await run(() => client ? api.updateClient(client.id, body) : api.createClient(body))) { toast('Client enregistré'); onDone() }
  }
  return (
    <Modal title={client ? `Modifier ${client.nom}` : 'Nouveau client'} onClose={onClose} large
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || f.nom.length < 2} onClick={save}>Enregistrer</button></>}>
      <ErrorBox error={error} />
      <div className="form-grid">
        <Field label="Nom de l'instance" full><input className="input" value={f.nom} onChange={set('nom')} /></Field>
        <Field label="Type"><select className="input" value={f.type} onChange={set('type')}>{[...INSTANCES.filter((i) => i !== 'Autre'), 'Syndicat', 'Autre'].map((t) => <option key={t}>{t}</option>)}</select></Field>
        <Field label="Entreprise"><input className="input" value={f.entreprise_mere} onChange={set('entreprise_mere')} /></Field>
        <Field label="Contact principal"><input className="input" value={f.contact_principal} onChange={set('contact_principal')} /></Field>
        <Field label="Email"><input className="input" type="email" value={f.email_contact} onChange={set('email_contact')} /></Field>
        <Field label="Téléphone"><input className="input" value={f.telephone} onChange={set('telephone')} /></Field>
        <Field label="Conditions de paiement"><input className="input" placeholder="Ex. 30 jours" value={f.conditions_paiement} onChange={set('conditions_paiement')} /></Field>
        {(attribuables.length > 0 || f.grille_tarifaire_id) && (
          <Field label="Tarif négocié" hint="Grilles « sur attribution ». Vide : tarif par défaut ou du type d'instance">
            <select className="input" value={attribuables.find((g) => g.versions.some((v) => v.id === f.grille_tarifaire_id))?.courante?.id ?? f.grille_tarifaire_id}
              onChange={set('grille_tarifaire_id')} disabled={!can('tarifs.gerer')}>
              <option value="">Tarif standard</option>
              {attribuables.map((g) => <option key={g.famille_id} value={g.courante!.id}>{g.nom}</option>)}
              {f.grille_tarifaire_id && !attribuables.some((g) => g.versions.some((v) => v.id === f.grille_tarifaire_id)) && <option value={f.grille_tarifaire_id}>Grille actuelle</option>}
            </select>
          </Field>
        )}
        {client && <label className="checkbox full"><input type="checkbox" checked={f.actif} onChange={(e) => setF({ ...f, actif: e.target.checked })} />Client actif</label>}
      </div>
    </Modal>
  )
}

/* ── Retranscripteurs ────────────────────────────────────────────────────── */
type Perf = { prestataire_id: string; missions_terminees: number; respect_delais: number | null; qualite: number | null; delai_moyen_jours: number | null; fiabilite_donnees: string }

export function RetranscripteursPage() {
  const { can, user } = useAuth()
  const { data, error, loading, reload } = useLoad(() => api.prestataires(false))
  const perfs = useLoad(() => can('prestataires.performance') ? api.performances() as Promise<Perf[]> : Promise.resolve([] as Perf[]))
  const [edit, setEdit] = useState<PrestataireFiche | 'new' | null>(null)
  const [secret, setSecret] = useState<{ email: string; mot_de_passe_temporaire: string } | null>(null)
  const action = useAction()
  const perf = (id: string) => perfs.data?.find((p) => p.prestataire_id === id)
  const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${Math.round(v * 100)} %`)

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Retranscripteurs</h1><p>Disponibilités, charge et indicateurs internes (jamais visibles des retranscripteurs).</p></div>
        {can('prestataires.gerer') && <button className="btn btn-primary" data-tour="retranscripteurs-nouveau" onClick={() => setEdit('new')}><Plus size={18} />Nouveau retranscripteur</button>}
      </div>
      <ErrorBox error={error ?? action.error} />
      <div className="card">
        {loading && !data ? <PageLoader /> : !data?.length ? <Empty icon={<Users size={24} />} title="Aucun retranscripteur" /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Nom</th><th>Disponibilité</th><th>En cours</th><th>Spécialités</th>
              {can('prestataires.performance') && <><th>Terminées</th><th>Délais tenus</th><th>Qualité</th></>}<th>Accès</th><th /></tr></thead>
            <tbody>{data.map((p) => {
              const pf = perf(p.id)
              return (
                <tr key={p.id} style={{ opacity: p.actif ? 1 : .55 }}>
                  <td><strong>{p.nom}</strong><div className="small muted">{p.email}</div></td>
                  <td><Pill tone={p.disponible ? 'green' : 'gray'} dot>{p.disponible ? 'Disponible' : 'Indisponible'}</Pill></td>
                  <td className="mono">{p.charge_actuelle}</td>
                  <td className="row" style={{ gap: 4 }}>{p.specialites.length ? p.specialites.map((s) => <Pill key={s} tone="primary">{s}</Pill>) : <span className="muted">—</span>}</td>
                  {can('prestataires.performance') && <>
                    <td className="mono">{pf?.missions_terminees ?? 0}</td>
                    <td className="mono">{pct(pf?.respect_delais)}</td>
                    <td className="mono">{pct(pf?.qualite)}{pf?.fiabilite_donnees === 'insuffisante' && <div className="small muted">données insuffisantes</div>}</td>
                  </>}
                  <td>{p.compte ? <span className="small">Dernière connexion<br />{fDate(p.compte.last_login)}</span> : <span className="small muted">Aucun accès</span>}</td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {user?.role === 'administratrice' && p.actif && (
                      <button className="btn btn-ghost btn-sm" disabled={action.busy} onClick={() => {
                        if (!p.compte || window.confirm(`Réinitialiser le mot de passe de ${p.nom} ?`)) {
                          action.run(async () => { setSecret(await api.compteprestataire(p.id)); reload() })
                        }
                      }}><KeyRound size={15} />{p.compte ? 'Réinitialiser' : 'Créer l’accès'}</button>
                    )}
                    {can('prestataires.gerer') && <button className="btn btn-ghost btn-sm" onClick={() => setEdit(p)}>Modifier</button>}
                  </td>
                </tr>
              )
            })}</tbody>
          </table></div>
        )}
      </div>
      {edit && <PrestaForm p={edit === 'new' ? null : edit} onClose={() => setEdit(null)} onDone={() => { setEdit(null); reload() }} />}
      {secret && <SecretModal email={secret.email} secret={secret.mot_de_passe_temporaire} onClose={() => setSecret(null)} />}
    </div>
  )
}

export function SecretModal({ email, secret, onClose }: { email: string; secret: string; onClose: () => void }) {
  return (
    <Modal title="Identifiants à transmettre" onClose={onClose}
      footer={<button className="btn btn-primary" onClick={onClose}>J'ai noté ces informations</button>}>
      <div className="stack">
        <Alert tone="warning">Ce mot de passe temporaire ne sera plus affiché. Transmettez-le par un canal distinct de l'email (téléphone, SMS). Un nouveau mot de passe sera exigé à la première connexion.</Alert>
        <Field label="Identifiant"><div className="secret">{email}</div></Field>
        <Field label="Mot de passe temporaire"><div className="secret">{secret}</div></Field>
        <button className="btn btn-secondary btn-sm" onClick={() => navigator.clipboard?.writeText(secret).then(() => toast('Copié'))}>Copier le mot de passe</button>
      </div>
    </Modal>
  )
}

function PrestaForm({ p, onClose, onDone }: { p: PrestataireFiche | null; onClose: () => void; onDone: () => void }) {
  const { user } = useAuth()
  const grilles = useLoad(() => api.catalogue('retranscripteur').catch(() => []))
  const [f, setF] = useState({
    nom: p?.nom ?? '', email: p?.email ?? '', telephone: p?.telephone ?? '', disponible: p?.disponible ?? true,
    actif: p?.actif ?? true, specialites: p?.specialites ?? [] as string[], notes_internes: p?.notes_internes ?? '',
    grille_tarifaire_id: p?.grille_tarifaire_id ?? '', iban: '',
  })
  const { busy, error, run } = useAction()
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  const save = async () => {
    const body: Record<string, unknown> = { nom: f.nom, email: f.email, telephone: f.telephone || null, disponible: f.disponible,
      specialites: f.specialites, notes_internes: f.notes_internes || null, grille_tarifaire_id: f.grille_tarifaire_id || null }
    if (p) body.actif = f.actif
    if (f.iban) body.iban = f.iban
    if (await run(() => p ? api.updatePrestataire(p.id, body) : api.createPrestataire(body))) { toast('Fiche enregistrée'); onDone() }
  }
  const toggle = (s: string) => setF({ ...f, specialites: f.specialites.includes(s) ? f.specialites.filter((x) => x !== s) : [...f.specialites, s] })
  const grillesRetrans = (grilles.data ?? []).filter((g) => g.courante && g.courante.application === 'attribuee')
  return (
    <Modal title={p ? `Modifier ${p.nom}` : 'Nouveau retranscripteur'} onClose={onClose} large
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || f.nom.length < 2 || !f.email} onClick={save}>Enregistrer</button></>}>
      <ErrorBox error={error} />
      <div className="form-grid">
        <Field label="Nom"><input className="input" value={f.nom} onChange={set('nom')} /></Field>
        <Field label="Email"><input className="input" type="email" value={f.email} onChange={set('email')} /></Field>
        <Field label="Téléphone"><input className="input" value={f.telephone} onChange={set('telephone')} /></Field>
        <Field label="Grille de rémunération" hint="Grilles « sur attribution » (ex. convention Togo). Vide : grille par défaut">
          <select className="input" value={grillesRetrans.find((g) => g.versions.some((v) => v.id === f.grille_tarifaire_id))?.courante?.id ?? f.grille_tarifaire_id}
            onChange={set('grille_tarifaire_id')}>
            <option value="">Grille standard</option>
            {grillesRetrans.map((g) => <option key={g.famille_id} value={g.courante!.id}>{g.nom}</option>)}
            {f.grille_tarifaire_id && !grillesRetrans.some((g) => g.versions.some((v) => v.id === f.grille_tarifaire_id)) && <option value={f.grille_tarifaire_id}>Grille actuelle</option>}
          </select>
        </Field>
        <div className="field full"><span className="label">Spécialités</span>
          <div className="chips">{INSTANCES.map((s) => <button type="button" key={s} className={`chip${f.specialites.includes(s) ? ' active' : ''}`} onClick={() => toggle(s)}>{s}</button>)}</div>
        </div>
        <label className="checkbox"><input type="checkbox" checked={f.disponible} onChange={(e) => setF({ ...f, disponible: e.target.checked })} />Disponible pour de nouvelles missions</label>
        {p && <label className="checkbox"><input type="checkbox" checked={f.actif} onChange={(e) => setF({ ...f, actif: e.target.checked })} />Fiche active</label>}
        {user?.role === 'administratrice' && (
          <Field label="IBAN" hint={p?.iban_renseigne ? 'Un IBAN est enregistré (chiffré). Saisir pour le remplacer.' : 'Stocké chiffré, visible uniquement par l’administratrice'} full>
            <input className="input" value={f.iban} onChange={set('iban')} autoComplete="off" />
          </Field>
        )}
        <Field label="Notes internes" full><textarea className="input" value={f.notes_internes} onChange={set('notes_internes')} /></Field>
      </div>
    </Modal>
  )
}
