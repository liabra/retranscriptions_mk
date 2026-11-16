import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { RapportConformite } from '@/components/Rapport'
import type { Mission, Rapport } from '@/lib/api'
import { makeUser, renderWithAuth } from './helpers'

vi.mock('@/lib/api', () => ({
  api: {
    notifications: vi.fn(async () => ({ non_lues: 2, email_configure: false, items: [] })),
    missions: vi.fn(async (): Promise<Mission[]> => [{
      affectation_id: 'a1', reference: '2026-CE-0001', titre: 'Plénière', instance: 'CSE Exemple', type_instance: 'CE',
      date_seance: null, duree_audio_minutes: 75, echeance: new Date(Date.now() + 5 * 86400000).toISOString(), urgent: true,
      en_retard: false, consignes: 'Respecter le modèle', etape: 'en_cours', etape_label: 'En cours', peut_deposer: true,
      audio: { disponible: true, nom_fichier: 'seance.mp3', taille_octets: 1024 * 1024 }, versions: [], corrections: [],
      attribue_le: '2026-11-01T10:00:00Z',
    }]),
  },
}))

const rapport: Rapport = {
  statut: 'non_conforme', resume: '20 % du texte ne respecte pas « Comic Sans MS 12 pt »',
  exigences: { police: 'Comic Sans MS', taille_pt: 12 }, caracteres_total: 100, taux_conformite: 80,
  polices: { 'Comic Sans MS': 80, Arial: 20 }, tailles: { '12 pt': 100 },
  anomalies: [{ zone: 'corps', paragraphe: 3, extrait: 'Texte en Arial', problemes: ['police « Arial »'], bloquant: true }],
  avertissements: [], pages_declarees: 4, mots: 20, paragraphes: 3,
}

describe('rapport de conformité', () => {
  it('affiche le taux et détaille les passages signalés', () => {
    render(<RapportConformite rapport={rapport} />)
    expect(screen.getByText('80 %')).toBeInTheDocument()
    expect(screen.queryByText(/Texte en Arial/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Détail du contrôle/ }))
    expect(screen.getByText(/Texte en Arial/)).toBeInTheDocument()
  })
})

describe('espace retranscripteur', () => {
  it('présente la mission sans aucune donnée financière', async () => {
    const { MesMissionsPage } = await import('@/pages/EspacesPages')
    const { container } = renderWithAuth(<MesMissionsPage />, makeUser({ role: 'retranscripteur', prestataire_id: 'p1', nom: 'Léa Durand' }))
    await waitFor(() => expect(screen.getByText('Plénière')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Télécharger l'audio/ })).toBeInTheDocument()
    expect(screen.getByText(/Respecter le modèle/)).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/€|tarif|montant|facture/i)
  })
})

describe('navigation', () => {
  it("masque les sections non autorisées et n'affiche pas la facturation sans droit", async () => {
    const { Layout } = await import('@/components/Layout')
    renderWithAuth(<Layout />, makeUser({ role: 'coordinatrice', permissions: ['dossiers.voir', 'audios.gerer'] }))
    expect(screen.getByRole('link', { name: /Dossiers/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Audios reçus/ })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Facturation/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Utilisateurs/ })).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText(/Notifications \(2 non lues\)/)).toBeInTheDocument())
  })
})

describe('jeton de session', () => {
  it("n'utilise pas le stockage persistant", async () => {
    const { tokenStore } = await import('@/services/api')
    tokenStore.set('abc')
    expect(sessionStorage.getItem('a2c_token')).toBe('abc')
    expect(localStorage.getItem('access_token')).toBeNull()
    tokenStore.clear()
    expect(tokenStore.get()).toBeNull()
  })
})
