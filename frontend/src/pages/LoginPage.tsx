import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { LockKeyhole } from 'lucide-react'
import { homeFor, useAuth } from '@/lib/session'
import { ErrorBox, Field } from '@/components/ui'
import { useAction } from '@/lib/hooks'

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, run } = useAction()

  if (user) return <Navigate to={homeFor(user)} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const u = await run(() => login(email.trim(), password))
    if (u) navigate(homeFor(u), { replace: true })
  }

  return (
    <div className="auth">
      <section className="auth-side">
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-mark" style={{ background: 'rgba(255,255,255,.18)', boxShadow: 'none' }}>A2C</div>
          <div>
            <div className="brand-name" style={{ color: '#fff' }}>A2C</div>
            <div className="brand-sub" style={{ color: 'rgba(255,255,255,.75)' }}>Retranscriptions</div>
          </div>
        </div>
        <div style={{ position: 'relative', zIndex: 1 }}>
          <h1>Des procès-verbaux fiables, livrés à temps.</h1>
          <p>Réception des audios, attribution, relecture, validation et facturation : tout le suivi de vos retranscriptions au même endroit.</p>
        </div>
        <p className="small" style={{ color: 'rgba(255,255,255,.7)', position: 'relative', zIndex: 1 }}>
          Accès réservé · données confidentielles des instances représentatives du personnel
        </p>
      </section>

      <section className="auth-form">
        <form className="auth-card" onSubmit={submit} noValidate>
          <div>
            <div className="eyebrow">Espace sécurisé</div>
            <h2 style={{ fontSize: 26, fontWeight: 650, marginTop: 6 }}>Connexion</h2>
            <p className="muted" style={{ marginTop: 4 }}>Utilisez l'adresse email de votre compte.</p>
          </div>
          <ErrorBox error={error} />
          <Field label="Email">
            <input className="input" type="email" autoComplete="username" required value={email}
              onChange={(e) => setEmail(e.target.value)} autoFocus />
          </Field>
          <Field label="Mot de passe">
            <input className="input" type="password" autoComplete="current-password" required value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <button className="btn btn-primary btn-lg btn-block" disabled={busy || !email || !password}>
            <LockKeyhole size={18} />{busy ? 'Connexion…' : 'Se connecter'}
          </button>
          <p className="small muted" style={{ textAlign: 'center' }}>
            Mot de passe oublié ? Contactez l'administratrice, qui pourra le réinitialiser.
          </p>
        </form>
      </section>
    </div>
  )
}
