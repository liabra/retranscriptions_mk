import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { dossiersService } from '@/services/dossiers.service'
import { clientsService } from '@/services/clients.service'
import type { Client, TypeInstance, NiveauConfidentialite } from '@/types'
import { getApiErrorMessage } from '@/services/api'
import { Spinner } from '@/components/ui/Spinner'

const TYPE_INSTANCES: TypeInstance[] = ['CE', 'CMAS', 'CSSCT', 'Autre']
const NIVEAUX: { value: NiveauConfidentialite; label: string }[] = [
  { value: 'standard', label: 'Standard' },
  { value: 'renforce', label: 'Renforcé' },
  { value: 'absolu', label: 'Absolu' },
]

export function DossierCreatePage() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<Client[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const [form, setForm] = useState({
    type_instance: 'CE' as TypeInstance,
    client_id: '',
    titre: '',
    date_seance: '',
    date_reception_audio: new Date().toISOString().slice(0, 16),
    date_limite: '',
    duree_audio_minutes: '',
    niveau_confidentialite: 'standard' as NiveauConfidentialite,
    notes_internes: '',
  })

  useEffect(() => {
    clientsService.list().then(setClients).catch(console.error)
  }, [])

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!form.client_id) { setError('Veuillez sélectionner un client'); return }
    setError('')
    setIsSubmitting(true)
    try {
      const dossier = await dossiersService.create({
        type_instance: form.type_instance,
        client_id: form.client_id,
        titre: form.titre || undefined,
        date_seance: form.date_seance || undefined,
        date_reception_audio: new Date(form.date_reception_audio).toISOString(),
        date_limite: form.date_limite || undefined,
        duree_audio_minutes: form.duree_audio_minutes ? parseInt(form.duree_audio_minutes) : undefined,
        niveau_confidentialite: form.niveau_confidentialite,
        notes_internes: form.notes_internes || undefined,
      })
      navigate(`/dossiers/${dossier.id}`)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="page">
      <div className="header-row">
        <div>
          <h1 className="page-title">Nouveau dossier</h1>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-muted)' }}>
            Réception d'un enregistrement audio
          </p>
        </div>
        <button className="btn btn-secondary" onClick={() => navigate('/dossiers')}>
          Annuler
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Informations du dossier</h2>
        </div>
        <div className="card-body">
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">
                  Type d'instance <span className="req">*</span>
                </label>
                <select className="form-select" value={form.type_instance} onChange={(e) => set('type_instance', e.target.value)} required>
                  {TYPE_INSTANCES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Client <span className="req">*</span>
                </label>
                <select className="form-select" value={form.client_id} onChange={(e) => set('client_id', e.target.value)} required>
                  <option value="">— Sélectionner —</option>
                  {clients.map((c) => (
                    <option key={c.id} value={c.id}>{c.nom} ({c.type})</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Titre / objet de la séance</label>
              <input className="form-input" value={form.titre} onChange={(e) => set('titre', e.target.value)} placeholder="Ex : Réunion CE ordinaire — mars 2025" />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Date de la séance</label>
                <input className="form-input" type="date" value={form.date_seance} onChange={(e) => set('date_seance', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">
                  Réception audio <span className="req">*</span>
                </label>
                <input className="form-input" type="datetime-local" value={form.date_reception_audio} onChange={(e) => set('date_reception_audio', e.target.value)} required />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Date limite de livraison</label>
                <input className="form-input" type="date" value={form.date_limite} onChange={(e) => set('date_limite', e.target.value)} />
                <span className="form-hint">Délai contractuel — déclenchera l'urgence si &lt; 48h</span>
              </div>
              <div className="form-group">
                <label className="form-label">Durée audio (minutes)</label>
                <input className="form-input" type="number" min="1" value={form.duree_audio_minutes} onChange={(e) => set('duree_audio_minutes', e.target.value)} placeholder="Ex : 120" />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Niveau de confidentialité</label>
                <select className="form-select" value={form.niveau_confidentialite} onChange={(e) => set('niveau_confidentialite', e.target.value)}>
                  {NIVEAUX.map((n) => <option key={n.value} value={n.value}>{n.label}</option>)}
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Notes internes</label>
              <textarea className="form-textarea" value={form.notes_internes} onChange={(e) => set('notes_internes', e.target.value)} placeholder="Commentaires confidentiels…" />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 4 }}>
              <button type="button" className="btn btn-secondary" onClick={() => navigate('/dossiers')}>
                Annuler
              </button>
              <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                {isSubmitting ? <Spinner size={14} /> : null}
                {isSubmitting ? 'Création…' : 'Créer le dossier'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
