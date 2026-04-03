import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { dossiersService } from '@/services/dossiers.service'
import { clientsService } from '@/services/clients.service'
import { affectationsService } from '@/services/affectations.service'
import { fichiersService } from '@/services/fichiers.service'
import { prestatairesService } from '@/services/prestataires.service'
import { calculsService } from '@/services/calculs.service'
import { facturesService } from '@/services/factures.service'
import { paiementsService } from '@/services/paiements.service'
import { journalService } from '@/services/journal.service'
import type {
  Dossier, Client, Affectation, AffectationCreate,
  FichierDossier, FichierCreate, Prestataire, StatutDossier,
  RoleAffectation, TypeDocument, CalculTarifaire, FactureClient,
  PaiementPrestataire, JournalEntry,
} from '@/types'
import { StatusBadge, UrgentBadge } from '@/components/ui/StatusBadge'
import { PageLoader } from '@/components/ui/Spinner'
import { UXHint } from '@/components/ui/UXHint'
import { formatDate, formatDateTime, isRetard, STATUT_LABELS } from '@/utils/statuts'
import { useAuth } from '@/features/auth/AuthContext'

// ─── Constants ───────────────────────────────────────────────────────────────

const TRANSITIONS: Partial<Record<StatutDossier, StatutDossier[]>> = {
  recu: ['en_qualification', 'bloque', 'incomplet'],
  en_qualification: ['estime', 'bloque', 'incomplet'],
  estime: ['a_attribuer', 'bloque', 'incomplet'],
  a_attribuer: ['en_retranscription', 'bloque'],
  en_retranscription: ['a_corriger', 'bloque'],
  a_corriger: ['en_correction', 'en_retranscription', 'bloque'],
  en_correction: ['en_mise_en_forme', 'a_corriger', 'bloque'],
  en_mise_en_forme: ['calcul_en_cours', 'bloque'],
  calcul_en_cours: ['a_valider', 'bloque'],
  a_valider: ['envoye', 'en_mise_en_forme', 'bloque'],
  envoye: ['facture', 'bloque'],
  facture: ['paye_entrant', 'bloque'],
  paye_entrant: ['prestataires_payes', 'bloque'],
  prestataires_payes: ['archive'],
  archive: [],
  bloque: ['recu', 'en_qualification', 'estime', 'a_attribuer', 'en_retranscription', 'a_corriger', 'en_correction'],
  incomplet: ['en_qualification'],
}

const TYPE_DOCUMENT_LABELS: Record<TypeDocument, string> = {
  audio_brut: 'Audio brut',
  retranscription_v1: 'Retranscription v1',
  retranscription_corrigee: 'Retranscription corrigée',
  document_paiement: 'Document de paiement',
  document_client: 'Document client',
  facture: 'Facture',
  autre: 'Autre',
}

const ROLE_AFFECTATION_LABELS: Record<RoleAffectation, string> = {
  retranscripteur: 'Retranscripteur',
  correcteur: 'Correcteur',
}

const STATUT_CALCUL_BADGE: Record<string, string> = {
  estimatif: 'badge-yellow',
  definitif: 'badge-green',
  ajuste: 'badge-orange',
}

const STATUT_CALCUL_LABELS: Record<string, string> = {
  estimatif: 'Estimatif',
  definitif: 'Validé',
  ajuste: 'Ajusté',
}

const STATUT_PAIEMENT_FACTURE_LABELS: Record<string, string> = {
  non_payee: 'Non payée',
  partiellement: 'Partiellement payée',
  soldee: 'Soldée',
}

const STATUT_PAIEMENT_PRESTA_LABELS: Record<string, string> = {
  a_payer: 'À payer',
  valide: 'Validé',
  paye: 'Payé',
}

const JOURNAL_TYPE_LABELS: Record<string, string> = {
  creation: 'Création',
  statut: 'Statut',
  affectation: 'Affectation',
  envoi: 'Envoi',
  paiement: 'Paiement',
  ajustement_tarifaire: 'Ajustement',
  note: 'Note',
  config_grille: 'Config. grille',
  calcul_tarifaire: 'Calcul',
  incident: 'Incident',
  archivage: 'Archivage',
  auth: 'Auth',
  acces_document: 'Document',
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--color-border-light)' }}>
      <span style={{ width: 180, flexShrink: 0, fontSize: 12, color: 'var(--color-text-muted)', paddingTop: 1 }}>{label}</span>
      <span style={{ fontSize: 13 }}>{value ?? '—'}</span>
    </div>
  )
}

function MoneyRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  const num = parseFloat(value)
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--color-border-light)' }}>
      <span style={{ fontSize: 13, color: highlight ? 'var(--color-text)' : 'var(--color-text-muted)' }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: highlight ? 700 : 400 }}>{isNaN(num) ? '—' : `${num.toFixed(2)} €`}</span>
    </div>
  )
}

function SectionCard({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="card-header">
        <h2 className="card-title">{title}</h2>
        {action}
      </div>
      <div className="card-body">{children}</div>
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function DossierDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()

  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [client, setClient] = useState<Client | null>(null)
  const [affectations, setAffectations] = useState<Affectation[]>([])
  const [fichiers, setFichiers] = useState<FichierDossier[]>([])
  const [prestataires, setPrestataires] = useState<Prestataire[]>([])
  const [calcul, setCalcul] = useState<CalculTarifaire | null>(null)
  const [facture, setFacture] = useState<FactureClient | null>(null)
  const [paiements, setPaiements] = useState<PaiementPrestataire[]>([])
  const [journal, setJournal] = useState<JournalEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [pageError, setPageError] = useState('')

  // Qualification form
  const [showQualifForm, setShowQualifForm] = useState(false)
  const [qualifForm, setQualifForm] = useState({
    urgence: false,
    sans_prise_de_note: false,
    prestation_speciale: false,
    type_prestation_speciale: '',
    volume_estime_pages: '',
  })
  const [qualifLoading, setQualifLoading] = useState(false)
  const [qualifError, setQualifError] = useState('')

  // Affectation form
  const [showAffectForm, setShowAffectForm] = useState(false)
  const [affectForm, setAffectForm] = useState<AffectationCreate>({ prestataire_id: '', type_role: 'retranscripteur' })
  const [affectError, setAffectError] = useState('')
  const [affectLoading, setAffectLoading] = useState(false)

  // Fichier form
  const [showFichierForm, setShowFichierForm] = useState(false)
  const [fichierForm, setFichierForm] = useState<FichierCreate>({ type_document: 'autre', nom_fichier: '', url_onedrive: '' })
  const [fichierError, setFichierError] = useState('')
  const [fichierLoading, setFichierLoading] = useState(false)

  // Calcul form
  const [showCalculForm, setShowCalculForm] = useState(false)
  const [calculPages, setCalculPages] = useState('')
  const [calculLoading, setCalculLoading] = useState(false)
  const [calculError, setCalculError] = useState('')

  // Ajustement form
  const [showAjustForm, setShowAjustForm] = useState(false)
  const [ajustMontant, setAjustMontant] = useState('')
  const [ajustMotif, setAjustMotif] = useState('')
  const [ajustLoading, setAjustLoading] = useState(false)

  // Facture form
  const [showFactureForm, setShowFactureForm] = useState(false)
  const [factureLoading, setFactureLoading] = useState(false)
  const [factureTva, setFactureTva] = useState(false)

  // Paiements
  const [paiementsLoading, setPaiementsLoading] = useState(false)

  // Transition
  const [transitionLoading, setTransitionLoading] = useState<StatutDossier | null>(null)

  const isAdminOrCoord = user?.role === 'administratrice' || user?.role === 'coordinatrice'
  const isCompta = user?.role === 'comptabilite'
  const canManageFinance = isAdminOrCoord || isCompta

  useEffect(() => {
    if (!id) return

    Promise.all([
      dossiersService.get(id),
      affectationsService.list(id),
      fichiersService.list(id),
      isAdminOrCoord || isCompta ? prestatairesService.list({ actif_only: true }) : Promise.resolve([]),
      journalService.getDossier(id, 20),
    ])
      .then(async ([d, aff, fich, presta, jrnl]) => {
        setDossier(d)
        setAffectations(aff)
        setFichiers(fich)
        setPrestataires(presta)
        setJournal(jrnl)

        // Initialiser le form de qualification depuis les critères existants
        if (d.criteres_tarif) {
          const c = d.criteres_tarif as Record<string, unknown>
          setQualifForm({
            urgence: Boolean(c.urgence),
            sans_prise_de_note: Boolean(c.sans_prise_de_note),
            prestation_speciale: Boolean(c.prestation_speciale),
            type_prestation_speciale: String(c.type_prestation_speciale ?? ''),
            volume_estime_pages: String(c.volume_estime_pages ?? ''),
          })
        }

        try {
          const c = await clientsService.get(d.client_id)
          setClient(c)
        } catch { /* non bloquant */ }

        if (d.calcul_tarifaire_id) {
          calculsService.get(d.calcul_tarifaire_id).then(setCalcul).catch(() => null)
        }
        facturesService.getByDossier(id).then(setFacture).catch(() => null)
        paiementsService.list(id).then(setPaiements).catch(() => null)
      })
      .catch((err) => setPageError(err?.response?.data?.detail ?? err.message ?? 'Erreur de chargement'))
      .finally(() => setIsLoading(false))
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  function prestaName(prestaId: string) {
    return prestataires.find((p) => p.id === prestaId)?.nom ?? '…'
  }

  // ─── Handlers ─────────────────────────────────────────────────────────────

  async function handleForceUrgent() {
    if (!id || !dossier) return
    try {
      const updated = await dossiersService.forceUrgent(id)
      setDossier(updated)
    } catch { alert('Erreur') }
  }

  async function handleTransition(statut: StatutDossier) {
    if (!id) return
    setTransitionLoading(statut)
    try {
      const updated = await dossiersService.transition(id, statut)
      setDossier(updated)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(typeof msg === 'string' ? msg : 'Erreur lors de la transition')
    } finally {
      setTransitionLoading(null)
    }
  }

  async function handleQualifSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!id) return
    setQualifError('')
    setQualifLoading(true)
    try {
      const criteres: Record<string, unknown> = {
        urgence: qualifForm.urgence,
        sans_prise_de_note: qualifForm.sans_prise_de_note,
        prestation_speciale: qualifForm.prestation_speciale,
      }
      if (qualifForm.type_prestation_speciale)
        criteres.type_prestation_speciale = qualifForm.type_prestation_speciale
      if (qualifForm.volume_estime_pages)
        criteres.volume_estime_pages = parseFloat(qualifForm.volume_estime_pages)

      const updated = await dossiersService.qualify(id, { criteres_tarif: criteres })
      setDossier(updated)
      setShowQualifForm(false)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setQualifError(typeof detail === 'string' ? detail : 'Erreur lors de la qualification')
    } finally {
      setQualifLoading(false)
    }
  }

  async function handleAffectSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!id) return
    setAffectError('')
    setAffectLoading(true)
    try {
      const created = await affectationsService.create(id, affectForm)
      setAffectations((prev) => [...prev, created])
      setShowAffectForm(false)
      setAffectForm({ prestataire_id: '', type_role: 'retranscripteur' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setAffectError(typeof detail === 'string' ? detail : 'Erreur')
    } finally {
      setAffectLoading(false)
    }
  }

  async function handleFichierSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!id) return
    setFichierError('')
    setFichierLoading(true)
    try {
      const created = await fichiersService.create(id, fichierForm)
      setFichiers((prev) => [...prev, created])
      setShowFichierForm(false)
      setFichierForm({ type_document: 'autre', nom_fichier: '', url_onedrive: '' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setFichierError(typeof detail === 'string' ? detail : 'Erreur')
    } finally {
      setFichierLoading(false)
    }
  }

  async function handleCalculer(e: React.FormEvent) {
    e.preventDefault()
    if (!id) return
    setCalculError('')
    setCalculLoading(true)
    try {
      const result = await calculsService.calculer(id, calculPages)
      setCalcul(result)
      setShowCalculForm(false)
      setCalculPages('')
      const d = await dossiersService.get(id)
      setDossier(d)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCalculError(typeof detail === 'string' ? detail : 'Erreur lors du calcul')
    } finally {
      setCalculLoading(false)
    }
  }

  async function handleValiderCalcul() {
    if (!calcul) return
    try {
      setCalcul(await calculsService.valider(calcul.id))
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(typeof detail === 'string' ? detail : 'Erreur')
    }
  }

  async function handleAjuster(e: React.FormEvent) {
    e.preventDefault()
    if (!calcul) return
    setAjustLoading(true)
    try {
      setCalcul(await calculsService.ajuster(calcul.id, ajustMontant, ajustMotif))
      setShowAjustForm(false)
      setAjustMontant('')
      setAjustMotif('')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(typeof detail === 'string' ? detail : 'Erreur')
    } finally {
      setAjustLoading(false)
    }
  }

  async function handleGenererFacture() {
    if (!id) return
    setFactureLoading(true)
    try {
      setFacture(await facturesService.generer(id, { tva_applicable: factureTva }))
      setShowFactureForm(false)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(typeof detail === 'string' ? detail : 'Erreur')
    } finally {
      setFactureLoading(false)
    }
  }

  async function handleUpdateFacturePaiement(statut: string) {
    if (!facture) return
    try {
      setFacture(await facturesService.updatePaiement(facture.id, statut))
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(typeof detail === 'string' ? detail : 'Erreur')
    }
  }

  async function handleGenererPaiements() {
    if (!id || !confirm('Générer les paiements prestataires ?')) return
    setPaiementsLoading(true)
    try {
      setPaiements(await paiementsService.generer(id))
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(typeof detail === 'string' ? detail : 'Erreur')
    } finally {
      setPaiementsLoading(false)
    }
  }

  async function handleUpdatePaiement(paiementId: string, statut: string) {
    try {
      const updated = await paiementsService.update(paiementId, { statut })
      setPaiements((prev) => prev.map((p) => (p.id === paiementId ? updated : p)))
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(typeof detail === 'string' ? detail : 'Erreur')
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  if (isLoading) return <PageLoader />
  if (pageError) return <div className="page"><div className="alert alert-error">{pageError}</div></div>
  if (!dossier) return null

  const retard = isRetard(dossier.date_limite) &&
    !['archive', 'envoye', 'facture', 'paye_entrant', 'prestataires_payes'].includes(dossier.statut)
  const disponibleTransitions = TRANSITIONS[dossier.statut] ?? []
  const retranscripteurAffecte = affectations.find(
    (a) => a.type_role === 'retranscripteur' && a.statut !== 'rejete',
  )
  const correcteurAffecte = affectations.find(
    (a) => a.type_role === 'correcteur' && a.statut !== 'rejete',
  )
  const criteres = dossier.criteres_tarif as Record<string, unknown> | null

  return (
    <div className="page">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="header-row">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/dossiers')} style={{ padding: '2px 0' }}>
              ← Dossiers
            </button>
          </div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {dossier.reference}
            <StatusBadge statut={dossier.statut} />
            <UrgentBadge estUrgent={dossier.est_urgent} estRetard={retard && !dossier.est_urgent} />
          </h1>
          {dossier.titre && <p className="page-subtitle">{dossier.titre}</p>}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {isAdminOrCoord && !dossier.est_urgent && (
            <button className="btn btn-secondary btn-sm" onClick={handleForceUrgent}>
              Forcer urgent
            </button>
          )}
        </div>
      </div>

      {/* ── Infos + Workflow ────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card">
          <div className="card-header"><h2 className="card-title">Informations</h2></div>
          <div className="card-body" style={{ padding: '4px 20px' }}>
            <InfoRow label="Référence" value={<strong>{dossier.reference}</strong>} />
            <InfoRow label="Type d'instance" value={<span className="badge badge-gray">{dossier.type_instance}</span>} />
            <InfoRow label="Client" value={client?.nom ?? '…'} />
            <InfoRow label="Statut" value={<StatusBadge statut={dossier.statut} />} />
            <InfoRow label="Confidentialité" value={dossier.niveau_confidentialite} />
            <InfoRow label="Date de séance" value={formatDate(dossier.date_seance)} />
            <InfoRow label="Réception audio" value={formatDateTime(dossier.date_reception_audio)} />
            <InfoRow label="Date limite" value={
              <span style={retard ? { color: 'var(--color-danger)', fontWeight: 600 } : {}}>
                {formatDate(dossier.date_limite)}{retard && ' ⚠️'}
              </span>
            } />
            <InfoRow label="Durée audio" value={dossier.duree_audio_minutes ? `${dossier.duree_audio_minutes} min` : null} />
            <InfoRow label="Pages finales" value={dossier.nombre_pages_final ? String(dossier.nombre_pages_final) : null} />
          </div>
        </div>

        <div className="card">
          <div className="card-header"><h2 className="card-title">Workflow</h2></div>
          <div className="card-body">
            <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 12 }}>
              Statut actuel : <strong style={{ color: 'var(--color-text)' }}>{STATUT_LABELS[dossier.statut]}</strong>
            </div>
            {isAdminOrCoord && disponibleTransitions.length > 0 ? (
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 8 }}>
                  Transitions disponibles
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {disponibleTransitions.map((cible) => (
                    <button
                      key={cible}
                      className="btn btn-sm btn-secondary"
                      style={cible === 'bloque' ? { borderColor: 'var(--color-danger)', color: 'var(--color-danger)' } : {}}
                      disabled={transitionLoading !== null}
                      onClick={() => handleTransition(cible)}
                    >
                      {transitionLoading === cible ? '…' : `→ ${STATUT_LABELS[cible]}`}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="badge badge-gray" style={{ fontSize: 12 }}>
                {disponibleTransitions.length === 0 ? 'Statut terminal' : 'Transitions réservées admin/coord'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Notes internes (admin/coord seulement) ─────────────────────── */}
      {isAdminOrCoord && dossier.notes_internes && (
        <SectionCard title="Notes internes" action={<span className="badge badge-orange">Confidentiel</span>}>
          <p style={{ margin: 0, fontSize: 13, whiteSpace: 'pre-wrap' }}>{dossier.notes_internes}</p>
        </SectionCard>
      )}

      {/* ── Section Qualification ──────────────────────────────────────── */}
      {isAdminOrCoord && (
        <SectionCard
          title="Qualification"
          action={
            <button className="btn btn-sm btn-secondary" onClick={() => setShowQualifForm((v) => !v)}>
              {showQualifForm ? 'Annuler' : criteres ? 'Modifier' : 'Saisir les critères'}
            </button>
          }
        >
          {!criteres && !showQualifForm && (
            <UXHint hintId="dossier_qualification">
              La qualification permet de définir les critères tarifaires du dossier : urgence, type de prestation,
              volume estimé en pages. Ces critères sont utilisés par le moteur de calcul pour calculer
              automatiquement les montants client et prestataires. À remplir avant le calcul tarifaire.
            </UXHint>
          )}
          {showQualifForm ? (
            <form onSubmit={handleQualifSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <input type="checkbox" checked={qualifForm.urgence}
                    onChange={(e) => setQualifForm((f) => ({ ...f, urgence: e.target.checked }))} />
                  Mission urgente
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <input type="checkbox" checked={qualifForm.sans_prise_de_note}
                    onChange={(e) => setQualifForm((f) => ({ ...f, sans_prise_de_note: e.target.checked }))} />
                  Sans prise de note (SNP)
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <input type="checkbox" checked={qualifForm.prestation_speciale}
                    onChange={(e) => setQualifForm((f) => ({ ...f, prestation_speciale: e.target.checked }))} />
                  Prestation spéciale
                </label>
                {qualifForm.prestation_speciale && (
                  <div>
                    <label className="form-label">Type de prestation spéciale</label>
                    <input className="form-input" value={qualifForm.type_prestation_speciale}
                      onChange={(e) => setQualifForm((f) => ({ ...f, type_prestation_speciale: e.target.value }))}
                      placeholder="ex: prise_de_note, expertise…" />
                  </div>
                )}
                <div>
                  <label className="form-label">Volume estimé (pages)</label>
                  <input className="form-input" type="number" step="0.5" min="0"
                    value={qualifForm.volume_estime_pages}
                    onChange={(e) => setQualifForm((f) => ({ ...f, volume_estime_pages: e.target.value }))}
                    placeholder="ex: 45" />
                </div>
              </div>
              {qualifError && <div className="alert alert-error" style={{ marginTop: 8 }}>{qualifError}</div>}
              <div style={{ marginTop: 12 }}>
                <button type="submit" className="btn btn-primary btn-sm" disabled={qualifLoading}>
                  {qualifLoading ? '…' : 'Enregistrer'}
                </button>
              </div>
            </form>
          ) : criteres ? (
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <CritereTag label="Urgent" value={Boolean(criteres.urgence)} />
              <CritereTag label="SNP" value={Boolean(criteres.sans_prise_de_note)} />
              <CritereTag label="Spécial" value={Boolean(criteres.prestation_speciale)} />
              {Boolean(criteres.type_prestation_speciale) && (
                <div style={{ fontSize: 13 }}>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: 11 }}>Type spécial</span><br />
                  {String(criteres.type_prestation_speciale)}
                </div>
              )}
              {Boolean(criteres.volume_estime_pages) && (
                <div style={{ fontSize: 13 }}>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: 11 }}>Volume estimé</span><br />
                  {String(criteres.volume_estime_pages)} pages
                </div>
              )}
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
              Aucun critère de qualification saisi. Ces informations sont nécessaires avant le calcul tarifaire.
            </p>
          )}
        </SectionCard>
      )}

      {/* ── Section Affectations ───────────────────────────────────────── */}
      {isAdminOrCoord && (
        <SectionCard
          title="Affectations"
          action={
            <button className="btn btn-sm btn-primary" onClick={() => setShowAffectForm((v) => !v)}>
              {showAffectForm ? 'Annuler' : '+ Affecter'}
            </button>
          }
        >
          {affectations.length === 0 && !showAffectForm && (
            <UXHint hintId="dossier_affectation">
              Affectez un <strong>retranscripteur</strong> et un <strong>correcteur</strong> à ce dossier.
              Une fois affectés, ils accèdent au dossier depuis leur espace "Mes missions" et peuvent
              déclarer la livraison. L'affectation est nécessaire avant de lancer le calcul tarifaire.
            </UXHint>
          )}
          <div style={{ display: 'flex', gap: 32, marginBottom: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>Retranscripteur</div>
              {retranscripteurAffecte
                ? <span style={{ fontSize: 13 }}>{prestaName(retranscripteurAffecte.prestataire_id)} <span className="badge badge-gray">{retranscripteurAffecte.statut}</span></span>
                : <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Non affecté</span>}
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>Correcteur</div>
              {correcteurAffecte
                ? <span style={{ fontSize: 13 }}>{prestaName(correcteurAffecte.prestataire_id)} <span className="badge badge-gray">{correcteurAffecte.statut}</span></span>
                : <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Non affecté</span>}
            </div>
          </div>

          {showAffectForm && (
            <form onSubmit={handleAffectSubmit} style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: 16, marginBottom: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 10, alignItems: 'flex-end' }}>
                <div>
                  <label className="form-label">Prestataire</label>
                  <select className="form-input" value={affectForm.prestataire_id}
                    onChange={(e) => setAffectForm((f) => ({ ...f, prestataire_id: e.target.value }))} required>
                    <option value="">— Choisir —</option>
                    {prestataires.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.nom} ({p.role}){p.disponible ? '' : ' — indisponible'}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="form-label">Rôle</label>
                  <select className="form-input" value={affectForm.type_role}
                    onChange={(e) => setAffectForm((f) => ({ ...f, type_role: e.target.value as RoleAffectation }))}>
                    <option value="retranscripteur">Retranscripteur</option>
                    <option value="correcteur">Correcteur</option>
                  </select>
                </div>
                <button type="submit" className="btn btn-primary btn-sm" disabled={affectLoading}>
                  {affectLoading ? '…' : 'Affecter'}
                </button>
              </div>
              {affectError && <div className="alert alert-error" style={{ marginTop: 8 }}>{affectError}</div>}
            </form>
          )}

          {affectations.length > 0 && (
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  {['Prestataire', 'Rôle', 'Statut', 'Attribué le', 'Date limite'].map((h) => (
                    <th key={h} style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, fontSize: 11, color: 'var(--color-text-muted)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {affectations.map((a) => (
                  <tr key={a.id} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                    <td style={{ padding: '6px 8px' }}>{prestaName(a.prestataire_id)}</td>
                    <td style={{ padding: '6px 8px' }}>{ROLE_AFFECTATION_LABELS[a.type_role]}</td>
                    <td style={{ padding: '6px 8px' }}><span className="badge badge-gray">{a.statut}</span></td>
                    <td style={{ padding: '6px 8px' }}>{formatDate(a.date_attribution)}</td>
                    <td style={{ padding: '6px 8px' }}>{formatDate(a.date_limite_rendu)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>
      )}

      {/* ── Section Calcul tarifaire (admin/coord uniquement) ──────────── */}
      {isAdminOrCoord && (
        <SectionCard
          title="Calcul tarifaire"
          action={
            <div style={{ display: 'flex', gap: 8 }}>
              {calcul && calcul.statut !== 'definitif' && (
                <button className="btn btn-sm btn-secondary" onClick={() => setShowAjustForm((v) => !v)}>
                  {showAjustForm ? 'Annuler' : 'Ajuster'}
                </button>
              )}
              {calcul && calcul.statut !== 'definitif' && (
                <button className="btn btn-sm btn-primary" onClick={handleValiderCalcul}>Valider</button>
              )}
              <button className="btn btn-sm btn-secondary" onClick={() => setShowCalculForm((v) => !v)}>
                {showCalculForm ? 'Annuler' : calcul ? 'Recalculer' : 'Calculer'}
              </button>
            </div>
          }
        >
          {!calcul && !showCalculForm && (
            <UXHint hintId="dossier_calcul">
              Le calcul tarifaire applique automatiquement les grilles de tarifs configurées.
              Il nécessite : des <strong>critères de qualification</strong> saisis, des <strong>affectations</strong>
              prestataires actives, et des grilles tarifaires actives. Renseignez le nombre de pages final
              pour lancer le calcul. Vous pourrez ensuite ajuster manuellement et valider.
            </UXHint>
          )}
          {showCalculForm && (
            <form onSubmit={handleCalculer} style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: 16, marginBottom: 16 }}>
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
                <div style={{ flex: 1 }}>
                  <label className="form-label">Nombre de pages</label>
                  <input className="form-input" type="number" step="0.01" min="0"
                    value={calculPages}
                    onChange={(e) => setCalculPages(e.target.value)}
                    placeholder={dossier.nombre_pages_final ? String(dossier.nombre_pages_final) : 'ex: 45'}
                    required />
                </div>
                <button type="submit" className="btn btn-primary btn-sm" disabled={calculLoading}>
                  {calculLoading ? '…' : 'Lancer le calcul'}
                </button>
              </div>
              {calculError && <div className="alert alert-error" style={{ marginTop: 8 }}>{calculError}</div>}
            </form>
          )}

          {showAjustForm && calcul && (
            <form onSubmit={handleAjuster} style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: 16, marginBottom: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr auto', gap: 10, alignItems: 'flex-end' }}>
                <div>
                  <label className="form-label">Ajustement (€)</label>
                  <input className="form-input" type="number" step="0.01"
                    placeholder="-50 ou +30"
                    value={ajustMontant}
                    onChange={(e) => setAjustMontant(e.target.value)}
                    required />
                </div>
                <div>
                  <label className="form-label">Motif (obligatoire)</label>
                  <input className="form-input" value={ajustMotif}
                    onChange={(e) => setAjustMotif(e.target.value)} required />
                </div>
                <button type="submit" className="btn btn-primary btn-sm" disabled={ajustLoading}>
                  {ajustLoading ? '…' : 'Appliquer'}
                </button>
              </div>
            </form>
          )}

          {calcul ? (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <span className={`badge ${STATUT_CALCUL_BADGE[calcul.statut] ?? 'badge-gray'}`}>
                  {STATUT_CALCUL_LABELS[calcul.statut] ?? calcul.statut}
                </span>
                <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                  v{calcul.version_calcul} · {calcul.nombre_pages} pages · {formatDateTime(calcul.date_calcul)}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 6 }}>Côté client</div>
                  <MoneyRow label="Montant brut" value={calcul.montant_client_brut} />
                  {parseFloat(calcul.ajustement_client) !== 0 && (
                    <MoneyRow
                      label={`Ajustement${calcul.motif_ajustement_client ? ` — ${calcul.motif_ajustement_client}` : ''}`}
                      value={calcul.ajustement_client}
                    />
                  )}
                  <MoneyRow label="Montant final client" value={calcul.montant_client_final} highlight />
                </div>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 6 }}>Côté prestataires</div>
                  <MoneyRow label="Retranscripteur" value={calcul.montant_retranscripteur} />
                  <MoneyRow label="Correcteur" value={calcul.montant_correcteur} />
                  <MoneyRow label="Total prestataires" value={calcul.montant_prestataires_total} highlight />
                  <MoneyRow label="Marge brute" value={calcul.marge_brute} />
                </div>
              </div>

              {calcul.regles_appliquees && calcul.regles_appliquees.length > 0 && (
                <details style={{ marginTop: 12 }}>
                  <summary style={{ fontSize: 12, cursor: 'pointer', color: 'var(--color-text-muted)' }}>
                    Règles appliquées ({calcul.regles_appliquees.length})
                  </summary>
                  <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse', marginTop: 8 }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                        {['Règle', 'Cible', 'Valeur', 'Impact'].map((h) => (
                          <th key={h} style={{ textAlign: 'left', padding: '4px 6px', color: 'var(--color-text-muted)' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {calcul.regles_appliquees.map((r, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                          <td style={{ padding: '4px 6px' }}>{r.regle_libelle}</td>
                          <td style={{ padding: '4px 6px' }}><span className="badge badge-gray" style={{ fontSize: 10 }}>{r.cible}</span></td>
                          <td style={{ padding: '4px 6px' }}>{r.valeur_appliquee}</td>
                          <td style={{ padding: '4px 6px', fontWeight: 500 }}>
                            {parseFloat(r.impact_montant) >= 0 ? '+' : ''}{parseFloat(r.impact_montant).toFixed(2)} €
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              )}
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
              Aucun calcul tarifaire.{!criteres && ' Commencez par saisir les critères de qualification.'}
            </p>
          )}
        </SectionCard>
      )}

      {/* ── Section Facturation ────────────────────────────────────────── */}
      {canManageFinance && (
        <SectionCard
          title="Facturation"
          action={
            !facture && isAdminOrCoord ? (
              <button className="btn btn-sm btn-primary" onClick={() => setShowFactureForm((v) => !v)}>
                {showFactureForm ? 'Annuler' : 'Générer facture'}
              </button>
            ) : facture ? (
              <a
                href={facturesService.getPdfUrl(facture.id)}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-sm btn-secondary"
              >
                Voir la facture ↗
              </a>
            ) : undefined
          }
        >
          {!facture && !showFactureForm && calcul && (
            <UXHint hintId="dossier_facture">
              La facture est générée à partir du montant TTC issu du calcul tarifaire validé.
              Indiquez si la TVA est applicable (associations en règle générale non assujetties).
              Une fois générée, la facture est disponible en PDF et son statut de paiement
              peut être mis à jour (non payée → partiellement → soldée).
            </UXHint>
          )}
          {showFactureForm && (
            <div style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: 16, marginBottom: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 12 }}>
                <input type="checkbox" checked={factureTva} onChange={(e) => setFactureTva(e.target.checked)} />
                TVA applicable (20%)
              </label>
              <button className="btn btn-primary btn-sm" onClick={handleGenererFacture} disabled={factureLoading}>
                {factureLoading ? '…' : 'Confirmer'}
              </button>
            </div>
          )}

          {facture ? (
            <div>
              <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <strong style={{ fontSize: 15 }}>{facture.numero_facture}</strong>
                <span className={`badge ${facture.statut_paiement === 'soldee' ? 'badge-green' : facture.statut_paiement === 'partiellement' ? 'badge-yellow' : 'badge-gray'}`}>
                  {STATUT_PAIEMENT_FACTURE_LABELS[facture.statut_paiement] ?? facture.statut_paiement}
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13, marginBottom: 12 }}>
                <div>Émise le : <strong>{formatDate(facture.date_emission)}</strong></div>
                <div>Échéance : <strong>{formatDate(facture.date_echeance)}</strong></div>
                <div>Montant HT : <strong>{parseFloat(facture.montant_ht).toFixed(2)} €</strong></div>
                {facture.tva_applicable && (
                  <div>TVA ({facture.taux_tva}%) : <strong>{parseFloat(facture.montant_tva).toFixed(2)} €</strong></div>
                )}
                <div>Montant TTC : <strong style={{ fontSize: 15 }}>{parseFloat(facture.montant_ttc).toFixed(2)} €</strong></div>
              </div>
              {isAdminOrCoord && facture.statut_paiement !== 'soldee' && (
                <div style={{ display: 'flex', gap: 8 }}>
                  {facture.statut_paiement === 'non_payee' && (
                    <button className="btn btn-sm btn-secondary" onClick={() => handleUpdateFacturePaiement('partiellement')}>
                      Partiellement payée
                    </button>
                  )}
                  <button className="btn btn-sm btn-primary" onClick={() => handleUpdateFacturePaiement('soldee')}>
                    Marquer soldée
                  </button>
                </div>
              )}
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
              Aucune facture.{!calcul && ' Un calcul tarifaire est requis avant la facturation.'}
            </p>
          )}
        </SectionCard>
      )}

      {/* ── Section Paiements prestataires ────────────────────────────── */}
      {canManageFinance && (
        <SectionCard
          title="Paiements prestataires"
          action={
            paiements.length === 0 && isAdminOrCoord ? (
              <button className="btn btn-sm btn-primary" onClick={handleGenererPaiements} disabled={paiementsLoading}>
                {paiementsLoading ? '…' : 'Générer paiements'}
              </button>
            ) : undefined
          }
        >
          {paiements.length > 0 ? (
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  {['Prestataire', 'Rôle', 'Montant brut', 'Montant final', 'Statut', ''].map((h) => (
                    <th key={h} style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, fontSize: 11, color: 'var(--color-text-muted)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paiements.map((p) => (
                  <tr key={p.id} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                    <td style={{ padding: '6px 8px' }}>{prestaName(p.prestataire_id)}</td>
                    <td style={{ padding: '6px 8px', textTransform: 'capitalize' }}>{p.role_paye}</td>
                    <td style={{ padding: '6px 8px' }}>{parseFloat(p.montant_brut).toFixed(2)} €</td>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>{parseFloat(p.montant_final).toFixed(2)} €</td>
                    <td style={{ padding: '6px 8px' }}>
                      <span className={`badge ${p.statut === 'paye' ? 'badge-green' : p.statut === 'valide' ? 'badge-blue' : 'badge-gray'}`}>
                        {STATUT_PAIEMENT_PRESTA_LABELS[p.statut] ?? p.statut}
                      </span>
                    </td>
                    <td style={{ padding: '6px 8px' }}>
                      {p.statut === 'a_payer' && (
                        <button className="btn btn-ghost btn-sm" style={{ fontSize: 11 }}
                          onClick={() => handleUpdatePaiement(p.id, 'valide')}>Valider</button>
                      )}
                      {p.statut === 'valide' && (
                        <button className="btn btn-ghost btn-sm" style={{ fontSize: 11 }}
                          onClick={() => handleUpdatePaiement(p.id, 'paye')}>Marquer payé</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
              Aucun paiement prestataire.{!calcul && ' Un calcul tarifaire est requis.'}
            </p>
          )}
        </SectionCard>
      )}

      {/* ── Section Fichiers ───────────────────────────────────────────── */}
      <SectionCard
        title="Fichiers"
        action={
          isAdminOrCoord ? (
            <button className="btn btn-sm btn-primary" onClick={() => setShowFichierForm((v) => !v)}>
              {showFichierForm ? 'Annuler' : '+ Ajouter'}
            </button>
          ) : undefined
        }
      >
        {fichiers.length === 0 && !showFichierForm && (
          <UXHint hintId="dossier_fichiers">
            Les fichiers sont stockés sur <strong>OneDrive</strong> — seul le lien de partage est enregistré
            ici. Collez l'URL de partage OneDrive du fichier (audio, retranscription, facture…).
            Le lien doit être accessible aux personnes concernées sur votre tenant Microsoft 365.
          </UXHint>
        )}
        {showFichierForm && (
          <form onSubmit={handleFichierSubmit} style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: 16, marginBottom: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label className="form-label">Type de document</label>
                <select className="form-input" value={fichierForm.type_document}
                  onChange={(e) => setFichierForm((f) => ({ ...f, type_document: e.target.value as TypeDocument }))}>
                  {Object.entries(TYPE_DOCUMENT_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="form-label">Nom du fichier</label>
                <input className="form-input" type="text" placeholder="ex: CR_CE_2026-04.docx"
                  value={fichierForm.nom_fichier}
                  onChange={(e) => setFichierForm((f) => ({ ...f, nom_fichier: e.target.value }))}
                  required />
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">Lien OneDrive</label>
                <input className="form-input" type="url" placeholder="https://…"
                  value={fichierForm.url_onedrive}
                  onChange={(e) => setFichierForm((f) => ({ ...f, url_onedrive: e.target.value }))}
                  required />
              </div>
              <div>
                <label className="form-label">Version</label>
                <input className="form-input" type="text" placeholder="1.0"
                  value={fichierForm.version ?? ''}
                  onChange={(e) => setFichierForm((f) => ({ ...f, version: e.target.value }))} />
              </div>
              <div>
                <label className="form-label">Commentaire</label>
                <input className="form-input" type="text"
                  value={fichierForm.commentaire ?? ''}
                  onChange={(e) => setFichierForm((f) => ({ ...f, commentaire: e.target.value }))} />
              </div>
            </div>
            <div style={{ marginTop: 10 }}>
              <button type="submit" className="btn btn-primary btn-sm" disabled={fichierLoading}>
                {fichierLoading ? '…' : 'Ajouter'}
              </button>
            </div>
            {fichierError && <div className="alert alert-error" style={{ marginTop: 8 }}>{fichierError}</div>}
          </form>
        )}

        {fichiers.length > 0 ? (
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Nom', 'Type', 'Version', 'Statut', 'Date', ''].map((h) => (
                  <th key={h} style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, fontSize: 11, color: 'var(--color-text-muted)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fichiers.map((f) => (
                <tr key={f.id} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                  <td style={{ padding: '6px 8px' }}>{f.nom_fichier}</td>
                  <td style={{ padding: '6px 8px' }}>{TYPE_DOCUMENT_LABELS[f.type_document] ?? f.type_document}</td>
                  <td style={{ padding: '6px 8px' }}>{f.version}</td>
                  <td style={{ padding: '6px 8px' }}><span className="badge badge-gray">{f.statut}</span></td>
                  <td style={{ padding: '6px 8px' }}>{formatDate(f.created_at)}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                    <a href={f.url_onedrive} target="_blank" rel="noopener noreferrer"
                      className="btn btn-ghost btn-sm" style={{ fontSize: 12 }}>
                      Ouvrir ↗
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>Aucun fichier associé</p>
        )}
      </SectionCard>

      {/* ── Section Historique ─────────────────────────────────────────── */}
      <SectionCard title="Historique">
        {journal.length === 0 ? (
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>Aucun événement</p>
        ) : (
          <div style={{ maxHeight: 320, overflowY: 'auto' }}>
            {journal.map((entry) => (
              <div key={entry.id} style={{ display: 'flex', gap: 12, padding: '8px 0', borderBottom: '1px solid var(--color-border-light)', fontSize: 12 }}>
                <div style={{ width: 130, flexShrink: 0, color: 'var(--color-text-muted)', fontSize: 11 }}>
                  {formatDateTime(entry.timestamp)}
                </div>
                <div style={{ flex: 1 }}>
                  <span className="badge badge-gray" style={{ marginRight: 6, fontSize: 10 }}>
                    {JOURNAL_TYPE_LABELS[entry.type_action] ?? entry.type_action}
                  </span>
                  {entry.detail && (
                    <span style={{ color: 'var(--color-text-muted)' }}>
                      {typeof entry.detail.action === 'string' ? entry.detail.action.replace(/_/g, ' ') : ''}
                      {entry.detail.ancien && entry.detail.nouveau
                        ? ` : ${entry.detail.ancien} → ${entry.detail.nouveau}`
                        : ''}
                      {typeof entry.detail.motif === 'string' ? ` — ${entry.detail.motif}` : ''}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  )
}

// ─── Helper ──────────────────────────────────────────────────────────────────

function CritereTag({ label, value }: { label: string; value: boolean }) {
  return (
    <div style={{ fontSize: 13 }}>
      <span style={{ color: 'var(--color-text-muted)', fontSize: 11 }}>{label}</span><br />
      <span className={`badge ${value ? 'badge-blue' : 'badge-gray'}`}>{value ? 'Oui' : 'Non'}</span>
    </div>
  )
}
