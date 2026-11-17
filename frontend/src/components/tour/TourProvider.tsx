import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Lightbulb, X } from 'lucide-react'
import { useAuth } from '@/lib/session'
import { TOURS } from './tours'
import { TourContext, etapesVisibles } from './context'

interface Rect { top: number; left: number; width: number; height: number }

const MARGE = 8
const LARGEUR = 360

function trouverCible(target?: string): HTMLElement | null {
  if (!target) return null
  const el = document.querySelector<HTMLElement>(`[data-tour="${target}"]`)
  if (!el) return null
  const r = el.getBoundingClientRect()
  return r.width > 0 && r.height > 0 ? el : null  // masquée (menu mobile fermé…) : bulle centrée
}

export function TourProvider({ children }: { children: ReactNode }) {
  const [tourId, setTourId] = useState<string | null>(null)
  const [index, setIndex] = useState(0)
  const start = useCallback((id: string) => { if (TOURS[id]) { setIndex(0); setTourId(id) } }, [])
  const stop = useCallback(() => setTourId(null), [])
  const value = useMemo(() => ({ start, stop, actif: tourId }), [start, stop, tourId])
  return (
    <TourContext.Provider value={value}>
      {children}
      {tourId && <Overlay key={tourId} tourId={tourId} index={index} setIndex={setIndex} onClose={stop} />}
    </TourContext.Provider>
  )
}

function Overlay({ tourId, index, setIndex, onClose }: {
  tourId: string; index: number; setIndex: (i: number) => void; onClose: () => void
}) {
  const { can } = useAuth()
  const steps = useMemo(() => etapesVisibles(TOURS[tourId].steps, can), [tourId, can])
  const step = steps[Math.min(index, steps.length - 1)]
  const navigate = useNavigate()
  const location = useLocation()
  const [rect, setRect] = useState<Rect | null>(null)
  const [pretPour, setPretPour] = useState<number | null>(null)
  const pret = pretPour === index  // prêt = cible mesurée pour l'étape courante
  const bulle = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number; centre: boolean }>({ top: 0, left: 0, centre: true })
  const dernier = index >= steps.length - 1

  // Changement de page puis attente de l'élément ciblé
  useEffect(() => {
    if (!step) return
    let annule = false
    if (step.route && location.pathname !== step.route) navigate(step.route)
    const debut = Date.now()
    const chercher = () => {
      if (annule) return
      const el = trouverCible(step.target)
      if (el || !step.target || Date.now() - debut > 2500) {
        if (el) el.scrollIntoView({ block: 'center', behavior: 'instant' as ScrollBehavior })
        mesurer()
        setPretPour(index)
        return
      }
      window.setTimeout(chercher, 100)
    }
    const mesurer = () => {
      const el = trouverCible(step.target)
      if (!el) { setRect(null); return }
      const r = el.getBoundingClientRect()
      setRect({ top: r.top - MARGE, left: r.left - MARGE, width: r.width + 2 * MARGE, height: r.height + 2 * MARGE })
    }
    window.setTimeout(chercher, 50)
    const onChange = () => mesurer()
    window.addEventListener('resize', onChange)
    window.addEventListener('scroll', onChange, true)
    return () => { annule = true; window.removeEventListener('resize', onChange); window.removeEventListener('scroll', onChange, true) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, tourId])

  // Placement de la bulle : sous la cible, sinon au-dessus, sinon à côté, sinon au centre
  /* eslint-disable react-hooks/set-state-in-effect -- mesure du DOM : le placement dépend de la taille réelle de la bulle */
  useLayoutEffect(() => {
    const b = bulle.current
    if (!b) return
    const vw = window.innerWidth, vh = window.innerHeight
    const w = Math.min(LARGEUR, vw - 32), h = b.offsetHeight
    if (!rect || vw < 640) { setPos({ top: 0, left: 0, centre: true }); return }
    const clampX = (x: number) => Math.max(16, Math.min(x, vw - w - 16))
    const clampY = (y: number) => Math.max(16, Math.min(y, vh - h - 16))
    if (rect.top + rect.height + 12 + h < vh) setPos({ top: rect.top + rect.height + 12, left: clampX(rect.left), centre: false })
    else if (rect.top - 12 - h > 0) setPos({ top: rect.top - 12 - h, left: clampX(rect.left), centre: false })
    else if (rect.left + rect.width + 12 + w < vw) setPos({ top: clampY(rect.top), left: rect.left + rect.width + 12, centre: false })
    else if (rect.left - 12 - w > 0) setPos({ top: clampY(rect.top), left: rect.left - 12 - w, centre: false })
    else setPos({ top: 0, left: 0, centre: true })
  }, [rect, pret, index])
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => { if (pret) bulle.current?.focus() }, [pret, index])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowRight') { if (dernier) onClose(); else setIndex(index + 1) }
      else if (e.key === 'ArrowLeft' && index > 0) setIndex(index - 1)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [index, dernier, onClose, setIndex])

  if (!step) return null
  const style = pos.centre
    ? { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }
    : { top: pos.top, left: pos.left }

  return (
    <div className="tour-layer" aria-hidden={false}>
      <div className="tour-blocker" />
      {pret && rect && !pos.centre
        ? <div className="tour-spot" style={{ top: rect.top, left: rect.left, width: rect.width, height: rect.height }} />
        : <div className="tour-dim" />}
      <div ref={bulle} className={`tour-bubble${pret ? ' visible' : ''}`} style={style} role="dialog" aria-modal="true"
        aria-labelledby="tour-titre" tabIndex={-1}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <span className="eyebrow">{TOURS[tourId].titre} · {index + 1} / {steps.length}</span>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose} aria-label="Quitter la visite"><X size={16} /></button>
        </div>
        <h2 id="tour-titre" className="tour-title">{step.title}</h2>
        <p className="tour-body">{step.body}</p>
        {step.tip && <div className="tour-tip"><Lightbulb size={16} /><span><strong>Conseil · </strong>{step.tip}</span></div>}
        <div className="tour-progress" aria-hidden>
          {steps.map((_, i) => <span key={i} className={i <= index ? 'on' : ''} />)}
        </div>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>Quitter</button>
          <div className="row" style={{ gap: 8 }}>
            {index > 0 && <button className="btn btn-secondary btn-sm" onClick={() => setIndex(index - 1)}><ArrowLeft size={15} />Précédent</button>}
            <button className="btn btn-primary btn-sm" onClick={() => (dernier ? onClose() : setIndex(index + 1))}>
              {dernier ? 'Terminer' : <>Suivant<ArrowRight size={15} /></>}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
