import { useState } from 'react'
import { Link } from 'react-router-dom'
import { History, KeyRound, Lightbulb, PlayCircle, Plus, ShieldCheck, UserCog } from 'lucide-react'
import { useTour } from '@/components/tour/context'
import { TOURS, tourPourRole } from '@/components/tour/tours'
import { api, type Me } from '@/lib/api'
import { useAuth } from '@/lib/session'
import { fDateTime, ROLES } from '@/lib/format'
import { Alert, Empty, ErrorBox, Field, Modal, PageLoader, Pill } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'
import { SecretModal } from '@/pages/ReferentielsPages'
import { ChangePasswordForm } from '@/pages/MotDePassePage'

const ROLES_CREABLES = ['administratrice', 'coordinatrice', 'comptabilite', 'lecture_seule', 'retranscripteur', 'client']

/* ── Utilisateurs & droits ───────────────────────────────────────────────── */
export function UtilisateursPage() {
  const { user: moi } = useAuth()
  const { data, error, loading, reload } = useLoad(() => api.users())
  const [edit, setEdit] = useState<Me | 'new' | null>(null)
  const [secret, setSecret] = useState<{ email: string; mot_de_passe_temporaire: string } | null>(null)
  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Utilisateurs & droits</h1><p>Comptes d'accès et répartition des responsabilités entre l'administratrice et la coordinatrice.</p></div>
        <button className="btn btn-primary" data-tour="utilisateurs-nouveau" onClick={() => setEdit('new')}><Plus size={18} />Nouvel utilisateur</button>
      </div>
      <ErrorBox error={error} />
      <div className="card">
        {loading && !data ? <PageLoader /> : !data?.length ? <Empty icon={<UserCog size={24} />} title="Aucun utilisateur" /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Nom</th><th>Rôle</th><th>Statut</th><th>Dernière connexion</th><th /></tr></thead>
            <tbody>{data.map((u) => (
              <tr key={u.id} style={{ opacity: u.actif ? 1 : .55 }}>
                <td><strong>{u.nom}</strong>{u.id === moi?.id && <Pill tone="primary">Vous</Pill>}<div className="small muted">{u.email}</div></td>
                <td>{ROLES[u.role] ?? u.role}{u.permissions_personnalisees && Object.keys(u.permissions_personnalisees).length > 0 && <div className="small muted">droits personnalisés</div>}</td>
                <td>{!u.actif ? <Pill>Désactivé</Pill> : u.must_change_password ? <Pill tone="amber">Mot de passe à définir</Pill> : <Pill tone="green" dot>Actif</Pill>}</td>
                <td className="small">{fDateTime(u.last_login)}</td>
                <td style={{ textAlign: 'right' }}><button className="btn btn-ghost btn-sm" onClick={() => setEdit(u)}>Gérer</button></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
      {edit && <UserForm u={edit === 'new' ? null : edit} onClose={() => setEdit(null)}
        onDone={(s) => { setEdit(null); reload(); if (s) setSecret(s) }} />}
      {secret && <SecretModal email={secret.email} secret={secret.mot_de_passe_temporaire} onClose={() => setSecret(null)} />}
    </div>
  )
}

function UserForm({ u, onClose, onDone }: { u: Me | null; onClose: () => void; onDone: (s?: { email: string; mot_de_passe_temporaire: string }) => void }) {
  const { user: moi } = useAuth()
  const catalogue = useLoad(() => api.permissionsCatalogue())
  const prestataires = useLoad(() => api.prestataires())
  const clients = useLoad(() => api.clients())
  const [f, setF] = useState({ nom: u?.nom ?? '', email: u?.email ?? '', role: u?.role ?? 'coordinatrice', actif: u?.actif ?? true,
    prestataire_id: u?.prestataire_id ?? '', client_id: u?.client_id ?? '' })
  const [perms, setPerms] = useState<Record<string, boolean>>(u?.permissions_personnalisees ?? {})
  const { busy, error, run } = useAction()
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  const defauts = new Set(catalogue.data?.par_defaut[f.role] ?? [])
  const effectif = (code: string) => (code in perms ? perms[code] : defauts.has(code))
  const configurable = ['coordinatrice', 'comptabilite', 'lecture_seule'].includes(f.role)

  const save = async (reset = false) => {
    const res = await run(() => u
      ? api.updateUser(u.id, { nom: f.nom, email: f.email, role: f.role, actif: f.actif, permissions: configurable ? perms : undefined, reinitialiser_mot_de_passe: reset })
      : api.createUser({ nom: f.nom, email: f.email, role: f.role, prestataire_id: f.prestataire_id || null, client_id: f.client_id || null }))
    if (!res) return
    if (configurable && !u) await api.updateUser(res.user.id, { permissions: perms }).catch(() => undefined)
    toast('Utilisateur enregistré')
    onDone(res.mot_de_passe_temporaire ? { email: res.user.email, mot_de_passe_temporaire: res.mot_de_passe_temporaire } : undefined)
  }

  return (
    <Modal title={u ? `Gérer ${u.nom}` : 'Nouvel utilisateur'} onClose={onClose} large
      footer={<>
        {u && u.id !== moi?.id && <button className="btn btn-secondary" style={{ marginRight: 'auto' }} disabled={busy}
          onClick={() => { if (window.confirm('Générer un nouveau mot de passe temporaire ?')) save(true) }}><KeyRound size={16} />Réinitialiser le mot de passe</button>}
        <button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || f.nom.length < 2 || !f.email} onClick={() => save()}>Enregistrer</button>
      </>}>
      <div className="stack-lg">
        <ErrorBox error={error} />
        <div className="form-grid">
          <Field label="Nom"><input className="input" value={f.nom} onChange={set('nom')} /></Field>
          <Field label="Email de connexion"><input className="input" type="email" value={f.email} onChange={set('email')} /></Field>
          <Field label="Rôle">
            <select className="input" value={f.role} onChange={(e) => { setF({ ...f, role: e.target.value as Me['role'] }); setPerms({}) }} disabled={u?.id === moi?.id}>
              {ROLES_CREABLES.map((r) => <option key={r} value={r}>{ROLES[r]}</option>)}
            </select>
          </Field>
          {!u && f.role === 'retranscripteur' && (
            <Field label="Fiche retranscripteur"><select className="input" value={f.prestataire_id} onChange={set('prestataire_id')}>
              <option value="">Choisir…</option>{prestataires.data?.filter((p) => !p.compte).map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}</select></Field>
          )}
          {!u && f.role === 'client' && (
            <Field label="Client"><select className="input" value={f.client_id} onChange={set('client_id')}>
              <option value="">Choisir…</option>{clients.data?.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}</select></Field>
          )}
          {u && u.id !== moi?.id && <label className="checkbox"><input type="checkbox" checked={f.actif} onChange={(e) => setF({ ...f, actif: e.target.checked })} />Compte actif</label>}
        </div>
        {f.role === 'administratrice' && <Alert tone="info">L'administratrice dispose de tous les droits, dont la gestion des utilisateurs et la consultation des IBAN.</Alert>}
        {configurable && catalogue.data && (
          <div className="card">
            <div className="card-header"><h3 className="card-title row"><ShieldCheck size={18} />Droits</h3><span className="small muted">Pré-cochés selon le rôle, ajustables</span></div>
            <div className="card-body form-grid">
              {catalogue.data.permissions.map((p) => (
                <label key={p.code} className="checkbox">
                  <input type="checkbox" checked={effectif(p.code)} onChange={(e) => setPerms({ ...perms, [p.code]: e.target.checked })} />
                  <span>{p.libelle}</span>
                </label>
              ))}
            </div>
          </div>
        )}
        {!u && <p className="small muted">Un mot de passe temporaire sera généré et affiché une seule fois ; il devra être changé à la première connexion.</p>}
      </div>
    </Modal>
  )
}

/* ── Journal ─────────────────────────────────────────────────────────────── */
export function JournalPage() {
  const [type, setType] = useState('')
  const { data, error, loading } = useLoad(() => api.journalGlobal({ limit: 300, type_action: type || undefined }), [type])
  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Journal d'activité</h1><p>Trace immuable des actions : qui, quoi, quand. Il n'est jamais modifié ni effacé.</p></div>
        <select className="input" style={{ width: 240 }} value={type} onChange={(e) => setType(e.target.value)} aria-label="Filtrer">
          <option value="">Toutes les actions</option>
          <option value="auth">Connexions & comptes</option><option value="statut">Changements d'étape</option>
          <option value="affectation">Attributions</option><option value="acces_document">Documents</option>
          <option value="paiement">Facturation & paiements</option><option value="config_grille">Tarifs</option>
        </select>
      </div>
      <ErrorBox error={error} />
      <div className="card">
        {loading && !data ? <PageLoader /> : !data?.length ? <Empty icon={<History size={24} />} title="Aucune entrée" /> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th><th>Détail</th></tr></thead>
            <tbody>{data.map((e) => (
              <tr key={e.id}>
                <td className="small" style={{ whiteSpace: 'nowrap' }}>{fDateTime(e.timestamp)}</td>
                <td className="small">{e.utilisateur_nom ?? 'Système'}</td>
                <td><Pill>{e.type_action.toLowerCase().replace(/_/g, ' ')}</Pill></td>
                <td className="small muted ellipsis" style={{ maxWidth: 480 }}>
                  {Object.entries(e.detail ?? {}).filter(([, v]) => typeof v !== 'object').map(([k, v]) => `${k.replace(/_/g, ' ')} : ${v}`).join(' · ')}
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </div>
  )
}

/* ── Mon compte ──────────────────────────────────────────────────────────── */
export function ComptePage() {
  const { user, refresh } = useAuth()
  const action = useAction()
  const notifs = useLoad(() => api.notifications())
  return (
    <div className="page">
      <div className="page-head"><div><h1>Mon compte</h1><p>{user?.nom} · {user?.email} · {ROLES[user?.role ?? '']}</p></div></div>
      <div className="grid-2">
        <div className="card">
          <div className="card-header"><h3 className="card-title">Mot de passe</h3></div>
          <div className="card-body"><ChangePasswordForm onDone={() => toast('Mot de passe modifié')} /></div>
        </div>
        <div className="card">
          <div className="card-header"><h3 className="card-title">Notifications</h3></div>
          <div className="card-body stack">
            <ErrorBox error={action.error} />
            <p className="small muted">Les notifications apparaissent toujours dans la plateforme (cloche en haut de l'écran).</p>
            <label className="checkbox">
              <input type="checkbox" checked={!!user?.notif_email} disabled={action.busy}
                onChange={(e) => action.run(async () => { await api.preferences(e.target.checked); await refresh() })} />
              <span>Recevoir aussi les notifications par email</span>
            </label>
            {notifs.data && !notifs.data.email_configure && <Alert tone="warning">L'envoi d'emails n'est pas encore configuré sur la plateforme : seules les notifications internes sont actives.</Alert>}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Aide ────────────────────────────────────────────────────────────────── */
interface Fiche { titre: string; texte: string; lien?: { to: string; label: string; perm?: string } }

export function AidePage() {
  const { isPrestataire, isClient, can } = useAuth()
  const { start } = useTour()
  const tourId = tourPourRole(isPrestataire, isClient)
  const fiches: Fiche[] = isPrestataire ? [
    { titre: 'Trouver mes missions', texte: 'Toutes vos missions en cours sont dans « Mes missions », triées par échéance. Une mission en retard est signalée en rouge.', lien: { to: '/mes-missions', label: 'Ouvrir mes missions' } },
    { titre: 'Télécharger l’audio', texte: 'Cliquez sur « Télécharger l’audio » sur la carte de la mission. Le fichier vous est transmis par la plateforme : vous n’avez besoin d’aucun accès OneDrive.' },
    { titre: 'Déposer mon PV', texte: 'Le PV doit être au format Word (.docx), en Comic Sans MS taille 12. Après le dépôt, un contrôle automatique vous indique si la mise en forme est conforme. Vous pouvez redéposer une version tant que la relecture n’a pas commencé.' },
    { titre: 'Corrections', texte: 'Si une correction est demandée, le message apparaît sur la carte de la mission. Déposez simplement la nouvelle version : les précédentes sont conservées.' },
    { titre: 'Confidentialité', texte: 'Les audios et PV concernent des instances représentatives du personnel : ne les partagez jamais et supprimez vos copies locales après validation.' },
  ] : [
    { titre: 'Ajouter un audio', texte: 'Collez un lien de partage OneDrive ou déposez le fichier. Le lien est chiffré et n’est jamais montré aux retranscripteurs. Créez ensuite la mission en un clic.', lien: { to: '/audios', label: 'Ouvrir « Audios reçus »', perm: 'audios.gerer' } },
    { titre: 'Attribuer une mission', texte: 'La plateforme propose un classement des retranscripteurs (qualité, délais, charge, spécialités). Ce n’est qu’une aide : vous choisissez toujours. Sans historique suffisant, la mention « Historique insuffisant » s’affiche.', lien: { to: '/dossiers?production=a_attribuer', label: 'Voir les missions à attribuer', perm: 'attribution.gerer' } },
    { titre: 'Contrôle des PV', texte: 'Chaque dépôt est contrôlé (format Word réel, police Comic Sans MS, taille 12). Un document non conforme est conservé et signalé ; sa validation demande un motif.', lien: { to: '/dossiers?production=livre,a_relire,a_controler', label: 'Voir les PV à relire', perm: 'relecture' } },
    { titre: 'Facturation', texte: 'Une fois le PV validé : calculer, valider le montant, établir la facture puis enregistrer les règlements. Une facture n’est jamais supprimée : elle s’annule en conservant son numéro.', lien: { to: '/finance', label: 'Ouvrir la facturation', perm: 'finance.voir' } },
    { titre: 'Tarifs, majorations et délais', texte: 'Tout se règle dans « Tarifs & paramètres » : barèmes (avec un nouveau barème chaque année), majorations, délais de réalisation. Chaque changement crée une version datée et ne modifie jamais un dossier déjà calculé.', lien: { to: '/tarifs', label: 'Ouvrir les tarifs', perm: 'tarifs.gerer' } },
    { titre: 'Droits de l’équipe', texte: 'L’administratrice ajuste les droits de la coordinatrice et remplace les adresses de connexion dans « Utilisateurs & droits ».', lien: { to: '/utilisateurs', label: 'Ouvrir les utilisateurs', perm: 'utilisateurs.gerer' } },
  ]
  return (
    <div className="page">
      <div className="page-head"><div><h1>Aide</h1><p>Apprenez en manipulant, ou retrouvez une explication précise.</p></div></div>
      {tourId && (
        <section className="stack" data-tour="guide-parcours">
          <h2 className="section-title">Apprendre en pratiquant <span className="small muted">· interactif</span></h2>
          <div className="grid-2">
            <div className="card card-pad stack">
              <h3 className="section-title">Visite guidée de la plateforme</h3>
              <p className="muted">Des bulles de conseil vous montrent, page par page, où se trouve chaque fonction et à quoi elle sert.</p>
              <button className="btn btn-primary" style={{ alignSelf: 'flex-start' }} onClick={() => start(tourId)}><Lightbulb size={16} />Lancer la visite · {TOURS[tourId].duree}</button>
            </div>
            {!isPrestataire && (
              <div className="card card-pad stack">
                <h3 className="section-title">Parcours d'un PV, de l'audio à la facture</h3>
                <p className="muted">Un exemple fictif, étape par étape : de la réception de l'audio au règlement de la facture. Rien n'est enregistré.</p>
                <Link className="btn btn-secondary" style={{ alignSelf: 'flex-start' }} to="/aide/parcours"><PlayCircle size={16} />Démarrer le parcours · 5 min</Link>
              </div>
            )}
          </div>
          {!isPrestataire && <p className="hint">Dans la fiche d'un dossier, le bouton « Guide de cette page » explique chaque zone de l'écran.</p>}
        </section>
      )}
      <section className="stack">
        <h2 className="section-title">Fiches pratiques <span className="small muted">· à lire, pour retrouver une règle ou une étape</span></h2>
        <div className="grid-2">
          {fiches.map((f) => (
            <div key={f.titre} className="card card-pad stack" style={{ gap: 8 }}>
              <h3 className="section-title">{f.titre}</h3>
              <p className="muted">{f.texte}</p>
              {f.lien && (!f.lien.perm || can(f.lien.perm)) && <Link className="small" to={f.lien.to}>{f.lien.label} →</Link>}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
