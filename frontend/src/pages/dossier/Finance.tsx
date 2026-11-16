import { useState } from 'react'
import { Calculator, CheckCircle2, ExternalLink, FileDown, Receipt, Wallet } from 'lucide-react'
import { api, type Calcul, type DossierDetail, type Facture } from '@/lib/api'
import { downloadFile, openHtml } from '@/services/api'
import { useAuth } from '@/lib/session'
import { fDate, fMoney } from '@/lib/format'
import { Alert, Empty, ErrorBox, Field, Modal, PageLoader, Pill, StatutPill } from '@/components/ui'
import { toast, useAction, useLoad } from '@/lib/hooks'

export function Finance({ dossier, onChange }: { dossier: DossierDetail; onChange: () => void }) {
  const { can } = useAuth()
  const gerer = can('finance.gerer')
  const calculs = useLoad(() => api.calculs(dossier.id), [dossier.id, dossier.statut_facturation])
  const facture = useLoad(() => api.factureDossier(dossier.id).catch(() => null), [dossier.id, dossier.statut_facturation])
  const paiements = useLoad(() => api.paiementsDossier(dossier.id), [dossier.id, dossier.statut_facturation])
  const action = useAction()
  const [ajuster, setAjuster] = useState<Calcul | null>(null)
  const [emettre, setEmettre] = useState(false)
  const [encaisser, setEncaisser] = useState<Facture | null>(null)

  const reload = () => { calculs.reload(); facture.reload(); paiements.reload(); onChange() }
  const courant = calculs.data?.[0]
  const factureActive = facture.data && !facture.data.annulee_le ? facture.data : null
  const valide = ['valide', 'archive'].includes(dossier.statut_production)

  if (calculs.loading && !calculs.data) return <PageLoader />

  return (
    <div className="stack-lg">
      <ErrorBox error={action.error ?? calculs.error} />
      {!valide && <Alert tone="info">La facturation s'ouvre lorsque le PV est validé. Les montants restent confidentiels et ne sont jamais montrés aux retranscripteurs.</Alert>}

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title row"><Calculator size={18} />Calcul tarifaire</h3>
            {gerer && valide && !factureActive && (
              <button className="btn btn-secondary btn-sm" disabled={action.busy}
                onClick={() => action.run(async () => { await api.calculer(dossier.id); toast('Calcul effectué'); reload() })}>
                {courant ? 'Recalculer' : 'Calculer'}
              </button>
            )}
          </div>
          <div className="card-body stack">
            {!courant ? <p className="muted small">Aucun calcul. {valide ? `Nombre de pages validé : ${dossier.nombre_pages_final ?? '—'}.` : ''}</p> : (
              <>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <span className="muted small">Version {courant.version_calcul} · {Number(courant.nombre_pages)} pages</span>
                  <Pill tone={courant.statut === 'definitif' ? 'green' : 'amber'}>{courant.statut === 'definitif' ? 'Validé' : courant.statut === 'ajuste' ? 'Ajusté' : 'À valider'}</Pill>
                </div>
                <dl className="dl">
                  <dt>Montant client</dt><dd className="mono" style={{ fontSize: 18 }}>{fMoney(courant.montant_client_final)}</dd>
                  {Number(courant.ajustement_client) !== 0 && <><dt>dont ajustement</dt><dd>{fMoney(courant.ajustement_client)} — {courant.motif_ajustement_client}</dd></>}
                  <dt>Rémunération retranscripteur</dt><dd className="mono">{fMoney(courant.montant_retranscripteur)}</dd>
                  <dt>Marge brute</dt><dd className="mono">{fMoney(courant.marge_brute)}</dd>
                </dl>
                {courant.grilles_version_snap && (
                  <div className="small muted">
                    Paramètres appliqués (copie conservée) : {Object.values(courant.grilles_version_snap).map((g) => `${g.nom} v${g.version}`).join(' · ')}
                    {courant.criteres_appliques?._tarification && ` — tarifs en vigueur au ${fDate(courant.criteres_appliques._tarification.date_reference)}`}
                  </div>
                )}
                {!!courant.regles_appliquees?.length && (
                  <details>
                    <summary className="small" style={{ cursor: 'pointer', color: 'var(--primary)' }}>Comment ce montant est calculé</summary>
                    <table style={{ marginTop: 8 }}>
                      <tbody>
                        {courant.regles_appliquees.map((r, i) => (
                          <tr key={i}><td className="small">{r.cible === 'CLIENT' ? 'Client' : 'Retranscripteur'} · {r.regle_libelle}</td>
                            <td className="small mono" style={{ textAlign: 'right' }}>{fMoney(r.impact_montant)}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                )}
                {gerer && courant.statut !== 'definitif' && !factureActive && (
                  <div className="row">
                    <button className="btn btn-primary btn-sm" disabled={action.busy}
                      onClick={() => action.run(async () => { await api.validerCalcul(courant.id); toast('Calcul validé'); reload() })}>
                      <CheckCircle2 size={16} />Valider ce montant
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setAjuster(courant)}>Ajuster</button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title row"><Receipt size={18} />Facture</h3>
            <StatutPill type="facturation" value={dossier.statut_facturation} />
          </div>
          <div className="card-body stack">
            {!factureActive ? (
              <>
                {facture.data?.annulee_le && <p className="small muted">Facture {facture.data.numero_facture} annulée : {facture.data.motif_annulation}</p>}
                {dossier.statut_facturation === 'a_etablir' && gerer ? (
                  <button className="btn btn-primary" disabled={courant?.statut !== 'definitif'} onClick={() => setEmettre(true)}>
                    <Receipt size={17} />Établir la facture
                  </button>
                ) : <p className="muted small">Pas encore de facture.</p>}
                {dossier.statut_facturation === 'a_etablir' && courant?.statut !== 'definitif' && <p className="hint">Validez d'abord le calcul tarifaire.</p>}
              </>
            ) : (
              <>
                <dl className="dl">
                  <dt>Numéro</dt><dd>{factureActive.numero_facture}</dd>
                  <dt>Payeur</dt><dd>{factureActive.payeur_nom}</dd>
                  <dt>Montant TTC</dt><dd className="mono" style={{ fontSize: 18 }}>{fMoney(factureActive.montant_ttc)}</dd>
                  <dt>Encaissé</dt><dd className="mono">{fMoney(factureActive.montant_encaisse)}</dd>
                  <dt>Reste dû</dt><dd className="mono">{fMoney(factureActive.reste_a_encaisser)}</dd>
                  <dt>Échéance</dt><dd>{fDate(factureActive.date_echeance)} {factureActive.en_retard && <Pill tone="red">En retard</Pill>}</dd>
                </dl>
                <div className="row">
                  <button className="btn btn-secondary btn-sm" onClick={() => action.run(() => openHtml(`/factures/${factureActive.id}/html`))}><ExternalLink size={15} />Voir</button>
                  <button className="btn btn-secondary btn-sm" onClick={() => action.run(() => downloadFile(`/factures/${factureActive.id}/pdf`, `${factureActive.numero_facture}.pdf`))}><FileDown size={15} />PDF</button>
                  {gerer && Number(factureActive.reste_a_encaisser) > 0 && (
                    <button className="btn btn-primary btn-sm" onClick={() => setEncaisser(factureActive)}><Wallet size={15} />Enregistrer un règlement</button>
                  )}
                </div>
                {factureActive.encaissements.map((e) => (
                  <div key={e.id} className="small muted">Règlement du {fDate(e.date_encaissement)} · {fMoney(e.montant)}{e.mode ? ` · ${e.mode}` : ''}</div>
                ))}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h3 className="card-title row"><Wallet size={18} />Rémunération du retranscripteur</h3></div>
        {!paiements.data?.length ? <Empty icon={<Wallet size={22} />} title="Aucun paiement">Le paiement est préparé automatiquement à l'émission de la facture.</Empty> : (
          <div className="list">
            {paiements.data.map((p) => (
              <div key={p.id} className="list-item">
                <div className="list-main">
                  <div className="list-title">{p.prestataire_nom}</div>
                  <div className="small muted">{Number(p.nombre_pages)} pages{p.motif_ajustement ? ` · ajustement : ${p.motif_ajustement}` : ''}{p.date_virement ? ` · virement du ${fDate(p.date_virement)}` : ''}</div>
                </div>
                <span className="mono">{fMoney(p.montant_final)}</span>
                <StatutPill type="paiement" value={p.statut} />
              </div>
            ))}
          </div>
        )}
      </div>

      {ajuster && <Ajustement calcul={ajuster} onClose={() => setAjuster(null)} onDone={() => { setAjuster(null); reload() }} />}
      {emettre && <Emettre dossierId={dossier.id} montant={courant?.montant_client_final} onClose={() => setEmettre(false)} onDone={() => { setEmettre(false); reload() }} />}
      {encaisser && <Encaisser facture={encaisser} onClose={() => setEncaisser(null)} onDone={() => { setEncaisser(null); reload() }} />}
    </div>
  )
}

function Ajustement({ calcul, onClose, onDone }: { calcul: Calcul; onClose: () => void; onDone: () => void }) {
  const [montant, setMontant] = useState('')
  const [motif, setMotif] = useState('')
  const { busy, error, run } = useAction()
  return (
    <Modal title="Ajuster le montant client" onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || !montant || motif.length < 3}
          onClick={async () => { if (await run(() => api.ajusterCalcul(calcul.id, montant, motif))) onDone() }}>Enregistrer</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        <p className="small muted">Montant calculé : {fMoney(calcul.montant_client_brut)}. L'ajustement est tracé dans l'historique.</p>
        <Field label="Ajustement (€, négatif pour une remise)"><input className="input" type="number" step="0.01" value={montant} onChange={(e) => setMontant(e.target.value)} /></Field>
        <Field label="Motif"><input className="input" value={motif} onChange={(e) => setMotif(e.target.value)} /></Field>
      </div>
    </Modal>
  )
}

function Emettre({ dossierId, montant, onClose, onDone }: { dossierId: string; montant?: string; onClose: () => void; onDone: () => void }) {
  const [tva, setTva] = useState(false)
  const [taux, setTaux] = useState('20')
  const [echeance, setEcheance] = useState('')
  const { busy, error, run } = useAction()
  return (
    <Modal title="Établir la facture" onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy} onClick={async () => {
          const f = await run(() => api.genererFacture(dossierId, { tva_applicable: tva, taux_tva: taux, date_echeance: echeance || null }))
          if (f) { toast(`Facture ${f.numero_facture} créée`); onDone() }
        }}>Créer la facture</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        <p>Montant HT : <strong className="mono">{fMoney(montant)}</strong></p>
        <label className="checkbox"><input type="checkbox" checked={tva} onChange={(e) => setTva(e.target.checked)} /><span>TVA applicable</span></label>
        {tva && <Field label="Taux de TVA (%)"><input className="input" type="number" value={taux} onChange={(e) => setTaux(e.target.value)} /></Field>}
        <Field label="Date d'échéance de paiement"><input className="input" type="date" value={echeance} onChange={(e) => setEcheance(e.target.value)} /></Field>
        <p className="small muted">La facture ne pourra plus être supprimée : une erreur se corrige par annulation (le numéro est conservé).</p>
      </div>
    </Modal>
  )
}

export function Encaisser({ facture, onClose, onDone }: { facture: Facture; onClose: () => void; onDone: () => void }) {
  const [montant, setMontant] = useState(facture.reste_a_encaisser)
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [mode, setMode] = useState('virement')
  const [reference, setReference] = useState('')
  const { busy, error, run } = useAction()
  return (
    <Modal title={`Règlement — ${facture.numero_facture}`} onClose={onClose}
      footer={<><button className="btn btn-secondary" onClick={onClose}>Annuler</button>
        <button className="btn btn-primary" disabled={busy || !Number(montant)} onClick={async () => {
          if (await run(() => api.encaisser(facture.id, { montant, date_encaissement: date, mode, reference: reference || null }))) { toast('Règlement enregistré'); onDone() }
        }}>Enregistrer</button></>}>
      <div className="stack">
        <ErrorBox error={error} />
        <p className="small muted">Reste à encaisser : {fMoney(facture.reste_a_encaisser)}</p>
        <div className="form-grid">
          <Field label="Montant reçu (€)"><input className="input" type="number" step="0.01" value={montant} onChange={(e) => setMontant(e.target.value)} /></Field>
          <Field label="Date"><input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
          <Field label="Mode"><select className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="virement">Virement</option><option value="cheque">Chèque</option><option value="autre">Autre</option></select></Field>
          <Field label="Référence"><input className="input" value={reference} onChange={(e) => setReference(e.target.value)} /></Field>
        </div>
      </div>
    </Modal>
  )
}
