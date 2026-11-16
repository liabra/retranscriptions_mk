import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'
import { homeFor, useAuth } from '@/lib/session'
import { Alert, ErrorBox, Field } from '@/components/ui'
import { useAction } from '@/lib/hooks'

function regles(pwd: string) {
  return [
    { ok: pwd.length >= 12, label: '12 caractères minimum' },
    { ok: [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(pwd)).length >= 3,
      label: '3 types parmi : minuscules, majuscules, chiffres, symboles' },
  ]
}

export function ChangePasswordForm({ onDone }: { onDone?: () => void }) {
  const { setSession, user } = useAuth()
  const navigate = useNavigate()
  const [ancien, setAncien] = useState('')
  const [nouveau, setNouveau] = useState('')
  const [confirm, setConfirm] = useState('')
  const { busy, error, run } = useAction()
  const checks = regles(nouveau)
  const valide = checks.every((c) => c.ok) && nouveau === confirm

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const res = await run(() => api.changePassword(ancien, nouveau))
    if (res) {
      setSession(res.access_token, res.user)
      if (onDone) onDone()
      else navigate(homeFor(res.user), { replace: true })
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <ErrorBox error={error} />
      <Field label={user?.must_change_password ? 'Mot de passe temporaire' : 'Mot de passe actuel'}>
        <input className="input" type="password" autoComplete="current-password" value={ancien} onChange={(e) => setAncien(e.target.value)} />
      </Field>
      <Field label="Nouveau mot de passe">
        <input className="input" type="password" autoComplete="new-password" value={nouveau} onChange={(e) => setNouveau(e.target.value)} />
      </Field>
      <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
        {checks.map((c) => <li key={c.label} style={{ color: c.ok ? 'var(--green)' : 'var(--muted)' }}>{c.label}</li>)}
      </ul>
      <Field label="Confirmation">
        <input className="input" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      </Field>
      {confirm && confirm !== nouveau && <p className="small" style={{ color: 'var(--red)' }}>Les deux saisies ne correspondent pas.</p>}
      <button className="btn btn-primary btn-lg" disabled={busy || !ancien || !valide}>
        <ShieldCheck size={18} />{busy ? 'Enregistrement…' : 'Enregistrer le mot de passe'}
      </button>
    </form>
  )
}

export function MotDePassePage() {
  const { user, logout } = useAuth()
  return (
    <div className="auth" style={{ gridTemplateColumns: '1fr' }}>
      <section className="auth-form">
        <div className="auth-card">
          <div>
            <div className="eyebrow">Première connexion</div>
            <h2 style={{ fontSize: 24, fontWeight: 650, marginTop: 6 }}>Choisissez votre mot de passe</h2>
            <p className="muted" style={{ marginTop: 4 }}>Bonjour {user?.nom}, pour sécuriser votre compte, remplacez le mot de passe qui vous a été transmis.</p>
          </div>
          <Alert tone="info">Ce mot de passe est personnel : il ne doit être communiqué à personne, y compris à l'équipe A2C.</Alert>
          <ChangePasswordForm />
          <button className="btn btn-ghost" onClick={logout}>Se déconnecter</button>
        </div>
      </section>
    </div>
  )
}
