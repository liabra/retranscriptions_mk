import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { Rapport as R } from '@/lib/api'
import { Pill } from '@/components/ui'

const TONE: Record<string, string> = { conforme: 'green', avertissements: 'amber', non_conforme: 'red' }

export function RapportConformite({ rapport, ouvert = false }: { rapport?: R | null; ouvert?: boolean }) {
  const [open, setOpen] = useState(ouvert)
  if (!rapport) return null
  const tone = TONE[rapport.statut] ?? 'gray'
  const couleur = tone === 'green' ? 'var(--green)' : tone === 'amber' ? 'var(--amber)' : 'var(--red)'
  return (
    <div className="report">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div className="small" style={{ color: couleur, fontWeight: 600 }}>{rapport.resume}</div>
        <button className="btn btn-ghost btn-sm" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}Détail du contrôle
        </button>
      </div>
      <div>
        <div className="row small muted" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
          <span>Texte en {rapport.exigences.police} {rapport.exigences.taille_pt} pt</span>
          <span className="mono">{String(rapport.taux_conformite).replace('.', ',')} %</span>
        </div>
        <div className="meter"><span style={{ width: `${rapport.taux_conformite}%`, background: couleur }} /></div>
      </div>
      {open && (
        <div className="stack" style={{ gap: 10 }}>
          <div className="row small">
            <span className="muted">Polices :</span>
            {Object.entries(rapport.polices).map(([k, v]) => (
              <Pill key={k} tone={k.toLowerCase() === 'comic sans ms' ? 'green' : 'red'}>{k} · {v} car.</Pill>
            ))}
          </div>
          <div className="row small">
            <span className="muted">Tailles :</span>
            {Object.entries(rapport.tailles).map(([k, v]) => (
              <Pill key={k} tone={k === '12 pt' ? 'green' : 'amber'}>{k} · {v} car.</Pill>
            ))}
          </div>
          <div className="small muted">
            {rapport.paragraphes} paragraphes · {rapport.mots} mots
            {rapport.pages_declarees ? ` · ${rapport.pages_declarees} page${rapport.pages_declarees > 1 ? 's' : ''} (selon Word)` : ''}
          </div>
          {rapport.avertissements.map((a) => <div key={a} className="small" style={{ color: 'var(--amber)' }}>⚠ {a}</div>)}
          {rapport.anomalies.length > 0 && (
            <div>
              <div className="small" style={{ fontWeight: 600, marginBottom: 4 }}>Passages signalés</div>
              {rapport.anomalies.map((a, i) => (
                <div key={i} className="anomaly">
                  <Pill tone={a.bloquant ? 'red' : 'amber'}>§ {a.paragraphe}</Pill>
                  <div style={{ minWidth: 0 }}>
                    <div className="ellipsis">« {a.extrait || '…'} »</div>
                    <div className="muted">{a.zone} · {a.problemes.join(', ')}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
