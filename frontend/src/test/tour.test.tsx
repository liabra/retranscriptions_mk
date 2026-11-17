import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { TourProvider } from '@/components/tour/TourProvider'
import { etapesVisibles, guideVu, marquerGuideVu, useTour } from '@/components/tour/context'
import { TOURS, tourPourRole } from '@/components/tour/tours'
import { DemoPage } from '@/pages/demo/DemoPage'
import { PARCOURS, parcoursPour } from '@/pages/demo/registre'
import { Route, Routes, MemoryRouter } from 'react-router-dom'
import { render } from '@testing-library/react'
import { AuthContext } from '@/lib/session'
import { makeUser, renderWithAuth } from './helpers'

function Lanceur({ id }: { id: string }) {
  const { start } = useTour()
  return <button onClick={() => start(id)}>lancer</button>
}

describe('visite guidée', () => {
  it('masque les étapes dont on n’a pas le droit', () => {
    const can = (p: string) => p === 'dossiers.voir'
    const titres = etapesVisibles(TOURS.interface.steps, can).map((s) => s.title)
    expect(titres).toContain('Tous vos dossiers')
    expect(titres).not.toContain('Facturation & règlements')
    expect(titres).not.toContain('Utilisateurs & droits')
  })
  it('associe la bonne visite au rôle', () => {
    expect(tourPourRole(true, false)).toBe('prestataire')
    expect(tourPourRole(false, false)).toBe('interface')
    expect(tourPourRole(false, true)).toBeNull()
  })
  it('mémorise que le guide a été proposé', () => {
    expect(guideVu('u-test')).toBe(false)
    marquerGuideVu('u-test')
    expect(guideVu('u-test')).toBe(true)
  })
  it('navigue au clavier et se ferme avec Échap', async () => {
    renderWithAuth(<TourProvider><Lanceur id="dossier" /></TourProvider>, makeUser({ permissions: [] }), '/dossiers/1')
    fireEvent.click(screen.getByText('lancer'))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    expect(await screen.findByText('Deux suivis distincts')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'ArrowRight' })
    expect(await screen.findByText('La frise d’avancement')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'ArrowLeft' })
    expect(await screen.findByText('Deux suivis distincts')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})

describe('parcours de démonstration', () => {
  it('déroule un PV fictif de l’audio au règlement', () => {
    renderWithAuth(<DemoPage />, makeUser({ permissions: [] }), '/aide/parcours')
    expect(screen.getByText(/Mode démonstration/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('Ajouter un lien OneDrive'))
    fireEvent.click(screen.getByText('Créer la mission'))
    expect(screen.getByText(/Étape 2/)).toBeInTheDocument()
    fireEvent.click(screen.getByText(/Créer et passer à l'attribution/))
    fireEvent.click(screen.getAllByText('Choisir').find((b) => !b.closest('button')?.hasAttribute('disabled'))!)
    fireEvent.click(screen.getByText(/Envoyer mon PV/))
    expect(screen.getByText('Non conforme')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Déposer une version corrigée'))
    expect(screen.getAllByText('Conforme').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText('Voir côté responsable'))
    fireEvent.click(screen.getByText('Terminer la relecture'))
    fireEvent.click(screen.getByText('Valider définitivement'))
    fireEvent.click(screen.getByText("Établir la facture"))
    fireEvent.click(screen.getByText('Règlement reçu'))
    expect(screen.getByText('Parcours terminé')).toBeInTheDocument()
  })
})


describe('parcours interactifs', () => {
  it('sépare les parcours des responsables et des retranscripteurs', () => {
    expect(parcoursPour(false).map((p) => p.id)).toEqual(['pv', 'tarifs', 'delais', 'cas', 'equipe'])
    expect(parcoursPour(true).map((p) => p.id)).toEqual(['mission'])
  })

  it.each(PARCOURS.filter((p) => p.id !== 'pv').map((p) => [p.id, p] as const))('« %s » se déroule jusqu’au bout en cliquant sur le bouton qui pulse', (_id, p) => {
    const user = makeUser({ role: p.audience === 'prestataire' ? 'retranscripteur' : 'administratrice', permissions: [] })
    const value = { user, ready: true, login: async () => user, logout: () => undefined, setSession: () => undefined, refresh: async () => undefined,
      can: () => false, isPrestataire: p.audience === 'prestataire', isClient: false }
    const { container } = render(
      <AuthContext.Provider value={value}>
        <MemoryRouter initialEntries={[`/aide/parcours/${p.id}`]}>
          <Routes><Route path="/aide/parcours/:id" element={<DemoPage />} /><Route path="/aide" element={<div>page aide</div>} /></Routes>
        </MemoryRouter>
      </AuthContext.Provider>)
    for (let i = 0; i < 40 && !screen.queryByText('Parcours terminé'); i++) {
      const bouton = container.querySelector<HTMLButtonElement>('button.demo-pulse')
      expect(bouton, `étape ${i + 1} sans bouton d'action`).not.toBeNull()
      fireEvent.click(bouton!)
    }
    expect(screen.getByText('Parcours terminé')).toBeInTheDocument()
  })

  it('renvoie vers l’aide un parcours réservé à l’autre profil', () => {
    const user = makeUser({ role: 'retranscripteur', prestataire_id: 'p1' })
    renderWithAuth(<DemoPage />, user, '/aide/parcours')
    expect(screen.queryByText('Mode démonstration.')).not.toBeInTheDocument()
  })
})
