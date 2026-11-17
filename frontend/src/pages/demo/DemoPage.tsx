import { Link, Navigate, useParams } from 'react-router-dom'
import { ArrowLeft, Lightbulb } from 'lucide-react'
import { useAuth } from '@/lib/session'
import { Lecteur } from './moteur'
import { PARCOURS } from './registre'

export function DemoPage() {
  const { id = 'pv' } = useParams()
  const { isPrestataire } = useAuth()
  const parcours = PARCOURS.find((p) => p.id === id)
  if (!parcours || (parcours.audience === 'prestataire') !== isPrestataire) return <Navigate to="/aide" replace />
  return (
    <div className="page">
      <div className="page-head">
        <div><Link to="/aide" className="small row" style={{ gap: 6 }}><ArrowLeft size={15} />Aide</Link>
          <h1>{parcours.titre}</h1><p>{parcours.intro}</p></div>
      </div>
      <div className="demo-banner"><Lightbulb size={18} /><span><strong>Mode démonstration.</strong> Les noms et montants sont fictifs et rien n'est enregistré. Cliquez sur le bouton vert qui pulse (entouré d'un halo) pour avancer.</span></div>
      <Lecteur key={parcours.id} parcours={parcours} />
    </div>
  )
}
