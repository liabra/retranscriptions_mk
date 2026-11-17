import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CheckCircle2, Lightbulb, RotateCcw, Send } from 'lucide-react'

/** Moteur commun des parcours de démonstration : tout est simulé, rien n'est enregistré. */

export type Acteur = 'Responsable' | 'Retranscripteur·rice' | 'Plateforme' | 'Comptabilité' | 'Administratrice'
const ACTEUR_TONE: Record<Acteur, string> = {
  Responsable: 'primary', 'Retranscripteur·rice': 'blue', Plateforme: 'violet', Comptabilité: 'amber', Administratrice: 'primary',
}

export type Etat = Record<string, boolean | undefined>

export interface Etape {
  cle: string
  titre: string
  acteur: Acteur
  resume: string
  tips: string[]
  ecran: (next: () => void, etat: Etat, maj: (e: Etat) => void) => ReactNode
}

export interface Parcours {
  id: string
  titre: string
  resume: string
  intro: string
  duree: string
  audience: 'interne' | 'prestataire'
  etapes: Etape[]
  fin: { texte: string; lien?: { to: string; label: string } }
}

export function Ecran({ url, children }: { url: string; children: ReactNode }) {
  return (
    <div className="demo-screen">
      <div className="demo-screen-bar"><i /><i /><i /><span style={{ marginLeft: 8 }}>{url}</span></div>
      <div className="demo-screen-body">{children}</div>
    </div>
  )
}

export function Action({ children, onClick, icon }: { children: ReactNode; onClick: () => void; icon?: ReactNode }) {
  return <button className="btn btn-primary demo-pulse" onClick={onClick}>{icon}{children}</button>
}

export const Tip = ({ children }: { children: ReactNode }) => <div className="demo-tip"><Lightbulb size={16} /><span>{children}</span></div>

export function Lecteur({ parcours }: { parcours: Parcours }) {
  const { etapes } = parcours
  const [i, setI] = useState(0)
  const [max, setMax] = useState(0)
  const [fini, setFini] = useState(false)
  const [etat, setEtat] = useState<Etat>({})
  const maj = (e: Etat) => setEtat((s) => ({ ...s, ...e }))

  const aller = (n: number) => { setI(n); setMax((m) => Math.max(m, n)); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const suivant = () => (i >= etapes.length - 1 ? setFini(true) : aller(i + 1))
  const recommencer = () => { setFini(false); setI(0); setMax(0); setEtat({}) }
  const e = etapes[i]

  if (fini) {
    return (
      <div className="card card-pad stack" style={{ alignItems: 'center', textAlign: 'center', padding: 40 }}>
        <span className="kpi-icon tone-green" style={{ width: 56, height: 56 }}><CheckCircle2 size={28} /></span>
        <h2 style={{ fontSize: 24 }}>Parcours terminé</h2>
        <p className="muted" style={{ maxWidth: 520 }}>{parcours.fin.texte}</p>
        <div className="row">
          <button className="btn btn-secondary" onClick={recommencer}><RotateCcw size={16} />Recommencer</button>
          <Link className="btn btn-ghost" to="/aide">Retour à l'aide</Link>
          {parcours.fin.lien && <Link className="btn btn-primary" to={parcours.fin.lien.to}><Send size={16} />{parcours.fin.lien.label}</Link>}
        </div>
      </div>
    )
  }

  return (
    <div className="demo-layout">
      <nav className="demo-nav" aria-label="Étapes du parcours">
        {etapes.map((s, n) => (
          <button key={s.cle} disabled={n > max} className={`${n === i ? 'active' : ''}${n < i || n < max ? ' fait' : ''}`} onClick={() => aller(n)}>
            <span className="demo-num">{n < max && n !== i ? <CheckCircle2 size={14} /> : n + 1}</span><span>{s.titre}</span>
          </button>
        ))}
      </nav>
      <section className="stack-lg" key={e.cle}>
        <div className="stack" style={{ gap: 8 }}>
          <span className={`demo-actor tone-${ACTEUR_TONE[e.acteur]}`}>{e.acteur}</span>
          <h2 style={{ fontSize: 22 }}>Étape {i + 1} · {e.titre}</h2>
          <p className="muted">{e.resume}</p>
        </div>
        {e.ecran(suivant, etat, maj)}
        <div className="demo-tips">{e.tips.map((t) => <Tip key={t}>{t}</Tip>)}</div>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <button className="btn btn-ghost" disabled={i === 0} onClick={() => aller(i - 1)}><ArrowLeft size={16} />Étape précédente</button>
          {i < max && <button className="btn btn-secondary" onClick={suivant}>Étape suivante<ArrowRight size={16} /></button>}
        </div>
      </section>
    </div>
  )
}
