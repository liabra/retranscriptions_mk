import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { Guard } from '@/components/Guards'
import { makeUser, renderWithAuth } from './helpers'

const routes = [
  { path: '/mes-missions', element: <div>espace prestataire</div> },
  { path: '/tableau-de-bord', element: <div>tableau de bord</div> },
  { path: '/mot-de-passe', element: <div>changer le mot de passe</div> },
  { path: '/login', element: <div>connexion</div> },
]

describe('gardes de navigation', () => {
  it('redirige un retranscripteur hors des pages internes', () => {
    renderWithAuth(<Guard rule="interne" perm={['finance.voir']}><div>finance</div></Guard>,
      makeUser({ role: 'retranscripteur', prestataire_id: 'p1' }), '/finance', routes)
    expect(screen.queryByText('finance')).not.toBeInTheDocument()
    expect(screen.getByText('espace prestataire')).toBeInTheDocument()
  })
  it('refuse une page interne sans la permission requise', () => {
    renderWithAuth(<Guard rule="interne" perm={['finance.voir']}><div>finance</div></Guard>,
      makeUser({ role: 'coordinatrice', permissions: ['dossiers.voir'] }), '/finance', routes)
    expect(screen.getByText('tableau de bord')).toBeInTheDocument()
  })
  it('impose le changement de mot de passe', () => {
    renderWithAuth(<Guard rule="tous"><div>contenu</div></Guard>, makeUser({ must_change_password: true }), '/compte', routes)
    expect(screen.getByText('changer le mot de passe')).toBeInTheDocument()
  })
  it('renvoie vers la connexion sans session', () => {
    renderWithAuth(<Guard rule="tous"><div>contenu</div></Guard>, null, '/compte', routes)
    expect(screen.getByText('connexion')).toBeInTheDocument()
  })
  it('affiche la page si le droit est présent', () => {
    renderWithAuth(<Guard rule="interne" perm={['finance.voir']}><div>finance</div></Guard>,
      makeUser({ permissions: ['finance.voir'] }), '/finance', routes)
    expect(screen.getByText('finance')).toBeInTheDocument()
  })
})
