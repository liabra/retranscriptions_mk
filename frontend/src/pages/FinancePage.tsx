import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Receipt, Wallet } from 'lucide-react'
import { api, type Facture, type Paiement } from '@/lib/api'
import { useAuth } from '@/lib/session'
import { fDate, fMoney } from '@/lib/format'
import { Empty, ErrorBox, Field, Modal, PageLoader, Pill, StatutPill, Tabs } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'
import { Encaisser } from '@/pages/dossier/Finance'

type Vue = 'a_etablir' | 'attente' | 'reglees' | 'paiements' | 'paiements_effectues'

export function FinancePage() {
  const [params, setParams] = useSearchParams()
  const vue = (params.get('vue') as Vue) || 'a_etablir'
  const setVue = (v: Vue) => setParams({ vue: v })
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Facturation & règlements</h1>
          <p>Factures clients, encaissements et rémunération des retranscripteurs — trois suivis distincts de la production.</p>
        </div>
      </div>
      <div data-tour="finance-onglets"><Tabs value={vue} onChange={setVue} items={[
        { key: 'a_etablir', label: 'Factures à établir' }, { key: 'attente', label: 'En attente de règlement' },
        { key: 'reglees', label: 'Réglées' }, { key: 'paiements', label: 'Paiements à effectuer' },
        { key: 'paiements_effectues', label: 'Paiements effectués' },
      ]} /></div>
      {vue === 'a_etablir' && <AFacturer />}
      {(vue === 'attente' || vue === 'reglees') && <Factures vue={vue} />}
      {vue === 'paiements' && <Paiements vue="a_effectuer" />}
      {vue === 'paiements_effectues' && <Paiements vue="effectues" />}
    </div>
  )
}

function AFacturer() {
  const navigate = useNavigate()
  const { data, error, loading } = useLoad(() => api.factures('a_etablir'))
  if (loading && !data) return <PageLoader />
  return (
    <div className="card">
      <ErrorBox error={error} />
      {!data?.items.length ? <Empty icon={<Receipt size={24} />} title="Aucune facture à établir">Les dossiers apparaissent ici dès la validation du PV.</Empty> : (
        <div className="table-wrap"><table>
          <thead><tr><th>Dossier</th><th>Client</th><th>Pages</th><th>Calcul</th><th /></tr></thead>
          <tbody>{data.items.map((d) => (
            <tr key={d.id} className="clickable" onClick={() => navigate(`/dossiers/${d.id}`)}>
              <td><strong>{d.reference}</strong><div className="small muted">{d.titre}</div></td>
              <td>{d.client_nom}</td>
              <td className="mono">{d.nombre_pages_final ?? '—'}</td>
              <td>{d.calcul ? <span className="row"><span className="mono">{fMoney(d.calcul.montant_client_final)}</span>
                <Pill tone={d.calcul.statut === 'definitif' ? 'green' : 'amber'}>{d.calcul.statut === 'definitif' ? 'validé' : 'à valider'}</Pill></span>
                : <span className="muted">À calculer</span>}</td>
              <td style={{ textAlign: 'right' }}><span className="btn btn-secondary btn-sm">Ouvrir</span></td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
    </div>
  )
}

function Factures({ vue }: { vue: 'attente' | 'reglees' }) {
  const { can } = useAuth()
  const navigate = useNavigate()
  const { data, error, loading, reload } = useLoad(() => api.factures(vue), [vue])
  const [encaisser, setEncaisser] = useState<Facture | null>(null)
  if (loading && !data) return <PageLoader />
  const total = data?.items.reduce((s, f) => s + Number(f.reste_a_encaisser ?? 0), 0) ?? 0
  return (
    <div className="card">
      <ErrorBox error={error} />
      {vue === 'attente' && !!data?.items.length && <div className="card-header"><span className="muted">Total restant dû</span><strong className="mono">{fMoney(total)}</strong></div>}
      {!data?.items.length ? <Empty icon={<Receipt size={24} />} title="Aucune facture" /> : (
        <div className="table-wrap"><table>
          <thead><tr><th>Facture</th><th>Dossier</th><th>Payeur</th><th>TTC</th><th>Reste dû</th><th>Échéance</th><th /></tr></thead>
          <tbody>{data.items.map((f) => (
            <tr key={f.id}>
              <td><strong>{f.numero_facture}</strong><div className="small muted">{fDate(f.date_emission)}</div></td>
              <td><a onClick={() => navigate(`/dossiers/${f.dossier_id}`)} style={{ cursor: 'pointer' }}>{f.dossier_reference}</a></td>
              <td>{f.payeur_nom}</td>
              <td className="mono">{fMoney(f.montant_ttc)}</td>
              <td className="mono">{fMoney(f.reste_a_encaisser)}</td>
              <td>{fDate(f.date_echeance)} {f.en_retard && <Pill tone="red">En retard</Pill>}</td>
              <td style={{ textAlign: 'right' }}>
                {vue === 'attente' && can('finance.gerer') ? <button className="btn btn-primary btn-sm" onClick={() => setEncaisser(f)}>Règlement reçu</button>
                  : <StatutPill type="facturation" value={f.statut_paiement === 'soldee' ? 'reglee' : 'emise'} />}
              </td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
      {encaisser && <Encaisser facture={encaisser} onClose={() => setEncaisser(null)} onDone={() => { setEncaisser(null); reload() }} />}
    </div>
  )
}

function Paiements({ vue }: { vue: 'a_effectuer' | 'effectues' }) {
  const { can } = useAuth()
  const { data, error, loading, reload } = useLoad(() => api.paiements(vue), [vue])
  const [payer, setPayer] = useState<Paiement | null>(null)
  const action = useAction()
  if (loading && !data) return <PageLoader />
  const total = data?.reduce((s, p) => s + Number(p.montant_final), 0) ?? 0
  return (
    <div className="card">
      <ErrorBox error={error ?? action.error} />
      {!!data?.length && <div className="card-header"><span className="muted">{data.length} paiement(s)</span><strong className="mono">{fMoney(total)}</strong></div>}
      {!data?.length ? <Empty icon={<Wallet size={24} />} title="Aucun paiement">{vue === 'a_effectuer' ? 'Tout est à jour.' : ''}</Empty> : (
        <div className="table-wrap"><table>
          <thead><tr><th>Retranscripteur</th><th>Dossier</th><th>Pages</th><th>Montant</th><th>Statut</th><th /></tr></thead>
          <tbody>{data.map((p) => (
            <tr key={p.id}>
              <td><strong>{p.prestataire_nom}</strong>{p.motif_ajustement && <div className="small muted">Ajustement : {p.motif_ajustement}</div>}</td>
              <td>{p.dossier_reference}</td>
              <td className="mono">{Number(p.nombre_pages)}</td>
              <td className="mono">{fMoney(p.montant_final)}</td>
              <td><StatutPill type="paiement" value={p.statut} />{p.date_virement && <div className="small muted">le {fDate(p.date_virement)}</div>}</td>
              <td style={{ textAlign: 'right' }}>{can('finance.gerer') && p.statut === 'a_payer' && (
                <button className="btn btn-secondary btn-sm" disabled={action.busy}
                  onClick={() => action.run(async () => { await api.majPaiement(p.id, { statut: 'valide' }); reload() })}>Valider</button>)}
                {can('finance.gerer') && p.statut === 'valide' && <button className="btn btn-primary btn-sm" onClick={() => setPayer(p)}>Marquer payé</button>}
              </td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
      {payer && <MarquerPaye p={payer} onClose={() => setPayer(null)} onDone={() => { setPayer(null); reload() }} />}
    </div>
  )
}

function MarquerPaye({ p, onClose, onDone }: { p: Paiement; onClose: () => void; onDone: () => void }) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [ref, setRef] = useState('')
  const { busy, error, run } = useAction()
  return (
    <Modal title={`Paiement de ${p.prestataire_nom}`} onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || !date} onClick={async () => {
          if (await run(() => api.majPaiement(p.id, { statut: 'paye', date_virement: date, reference_virement: ref || null }))) { toast('Paiement enregistré'); onDone() }
        }}>Confirmer le virement</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        <p>Montant : <strong className="mono">{fMoney(p.montant_final)}</strong> · dossier {p.dossier_reference}</p>
        <div className="form-grid">
          <Field label="Date du virement"><input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field label="Référence"><input className="input" value={ref} onChange={(e) => setRef(e.target.value)} /></Field>
        </div>
        <p className="small muted">Un paiement effectué n'est plus modifiable.</p>
      </div>
    </Modal>
  )
}
