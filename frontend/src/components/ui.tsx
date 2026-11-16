import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Info, Upload, X, XCircle } from 'lucide-react'
import { getApiErrorMessage } from '@/services/api'
import { CONTROLE, FACTURATION, PAIEMENT, PRODUCTION } from '@/lib/format'

export function Spinner() {
  return <div className="spinner" role="status" aria-label="Chargement" />
}

export function PageLoader() {
  return <div className="page-loader"><Spinner /></div>
}

export function Pill({ tone = 'gray', children, dot = false }: { tone?: string; children: ReactNode; dot?: boolean }) {
  return <span className={`pill tone-${tone}${dot ? ' pill-dot' : ''}`}>{children}</span>
}

export function StatutPill({ type, value }: { type: 'production' | 'facturation' | 'paiement' | 'controle'; value: string }) {
  const map = { production: PRODUCTION, facturation: FACTURATION, paiement: PAIEMENT, controle: CONTROLE }[type]
  const s = map[value] ?? { label: value, tone: 'gray' }
  return <Pill tone={s.tone} dot>{s.label}</Pill>
}

export function Alert({ tone = 'info', children }: { tone?: 'info' | 'error' | 'warning' | 'success'; children: ReactNode }) {
  const Icon = { info: Info, error: XCircle, warning: AlertTriangle, success: CheckCircle2 }[tone]
  return <div className={`alert alert-${tone}`} role={tone === 'error' ? 'alert' : 'status'}><Icon size={18} /><div>{children}</div></div>
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null
  return <Alert tone="error">{getApiErrorMessage(error)}</Alert>
}

export function Empty({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <strong>{title}</strong>
      {children && <div className="small">{children}</div>}
      {action && <div style={{ marginTop: 8 }}>{action}</div>}
    </div>
  )
}

export function Modal({ title, onClose, children, footer, large }: {
  title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; large?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    ref.current?.querySelector<HTMLElement>('input, select, textarea, button:not(.modal-close)')?.focus()
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className={`modal${large ? ' modal-lg' : ''}`} role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="btn btn-ghost btn-icon modal-close" onClick={onClose} aria-label="Fermer"><X size={18} /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

export function Field({ label, hint, children, full }: { label: string; hint?: string; children: ReactNode; full?: boolean }) {
  return (
    <label className={`field${full ? ' full' : ''}`}>
      <span className="label">{label}</span>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </label>
  )
}

export function Tabs<T extends string>({ value, onChange, items }: {
  value: T; onChange: (v: T) => void; items: { key: T; label: string; count?: number | null }[]
}) {
  return (
    <div className="tabs" role="tablist">
      {items.map((it) => (
        <button key={it.key} role="tab" aria-selected={value === it.key}
          className={`tab${value === it.key ? ' active' : ''}`} onClick={() => onChange(it.key)}>
          {it.label}{it.count != null && <span className="count">{it.count}</span>}
        </button>
      ))}
    </div>
  )
}

export function FileDrop({ accept, onFile, label, hint, disabled }: {
  accept: string; onFile: (f: File) => void; label: string; hint?: string; disabled?: boolean
}) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  return (
    <div
      className={`drop${over ? ' over' : ''}`} role="button" tabIndex={0} aria-disabled={disabled}
      onClick={() => !disabled && input.current?.click()}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !disabled) input.current?.click() }}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f && !disabled) onFile(f) }}
    >
      <Upload size={22} color="var(--primary)" />
      <strong>{label}</strong>
      {hint && <span className="hint">{hint}</span>}
      <input ref={input} type="file" accept={accept} hidden
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = '' }} />
    </div>
  )
}
